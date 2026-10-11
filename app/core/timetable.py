import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.core.cache import SubjectsCache
from app.core.database import (
    ClassroomsOperations,
    CurriculaOperations,
    EventsOperations,
    SubjectsOperations,
)
from app.core.scraper import TimetableScraper
from app.models.courses import CourseCurriculum
from app.models.timetable import Subject, Timetable
from app.utils.custom_logger import CustomLogger


@dataclass(slots=True)
class SyncReport:
    """
    Outcome of one pass over the subscribed curricula.

    Mutable on purpose: the counters are filled while the pass runs.

    Attributes:
        updated: Curricula whose timetable had actually changed.
        skipped: Curricula whose hash matched, so nothing was written.
        errors: Curricula that failed, either with no course url or with a
            scrape that raised. A failure never stops the pass.
    """

    updated: int = 0
    skipped: int = 0
    errors: int = 0


class TimetableSync:
    def __init__(self, session: AsyncSession, logger: CustomLogger):
        self.session = session
        self.logger = logger
        self.curricula = CurriculaOperations(session, logger)
        self.subjects = SubjectsOperations(session, logger)
        self.events = EventsOperations(session, logger)
        self.classrooms = ClassroomsOperations(session, logger)
        self.cache = SubjectsCache(logger)
        self.scraper = TimetableScraper(logger)

    async def sync(
        self, pair: CourseCurriculum, force: bool = False, active_only: bool = True
    ) -> List[Subject]:
        """
        Brings the stored timetable in line with the site and returns the
        subjects of the curriculum.
        """
        subjects, _ = await self.__sync(pair, force, active_only)
        return subjects

    async def sync_subscribed(self) -> SyncReport:
        pairs = await self.curricula.list_subscribed()
        self.logger.info("found active curricula", count=len(pairs))
        if not pairs:
            return SyncReport()

        report = SyncReport()
        for index, pair in enumerate(pairs):
            await self.__sync_one(pair, report)
            if index < len(pairs) - 1:
                await asyncio.sleep(config.scraper.delay_between_timetable_requests)

        deleted = await self.classrooms.cleanup_unused()
        if deleted:
            self.logger.info("deleted unused classrooms", count=deleted)

        await self.session.commit()
        return report

    async def refresh_stale(self, subject_ids: Sequence[UUID]) -> bool:
        """
        Re-syncs every curriculum behind the given subjects whose timetable
        is older than the event TTL, or whose events went missing.
        """
        threshold = datetime.now(UTC) - timedelta(seconds=config.scraper.timetable_events_ttl)
        refreshed = False

        for pair in await self.curricula.list_by_subjects(subject_ids):
            curriculum = pair.curriculum
            fresh = is_fresh(curriculum.timetable_updated_at, threshold)

            if fresh and await self.curricula.has_events(curriculum.id):
                continue

            self.logger.info(
                "refreshing timetable",
                curriculum_id=str(curriculum.id),
                reason="no events in db" if fresh else "stale",
            )
            await self.sync(pair, force=fresh)
            refreshed = True

        return refreshed

    async def cleanup_stale_events(self) -> int:
        now = datetime.now(UTC)
        stale_before = now - timedelta(seconds=config.scraper.timetable_events_ttl * 2)

        deleted = await self.events.cleanup_stale(stale_before, protected_after=now)
        await self.session.commit()
        return deleted

    async def __sync(
        self, pair: CourseCurriculum, force: bool, active_only: bool
    ) -> Tuple[List[Subject], bool]:
        course, curriculum = pair.course, pair.curriculum
        timetable = await self.scraper.fetch(course.url, curriculum)

        changed = force or curriculum.timetable_hash != timetable.content_hash
        if changed:
            await self.__apply(curriculum.id, timetable)
        else:
            self.logger.info(
                "timetable unchanged, skipping update",
                course_id=str(course.id),
                curriculum_id=str(curriculum.id),
            )

        # Written even when nothing changed: the timestamp is what marks the
        # curriculum as freshly checked.
        await self.curricula.touch_timetable(curriculum.id, timetable.content_hash)
        await self.session.commit()

        subjects = await self.subjects.list_by_curriculum(curriculum.id, active_only)
        await self.__refresh_cache(curriculum.id, subjects, active_only)
        return subjects, changed

    async def __apply(self, curriculum_id: UUID, timetable: Timetable) -> None:
        classrooms = await self.classrooms.upsert_many(timetable.classrooms())
        subjects = await self.subjects.sync(curriculum_id, timetable.subjects())
        await self.events.sync(list(subjects.values()), timetable.events, subjects, classrooms)

    async def __sync_one(self, pair: CourseCurriculum, report: SyncReport) -> None:
        curriculum_id = str(pair.curriculum.id)

        if not pair.course.url:
            self.logger.warning("no course url for curriculum", curriculum_id=curriculum_id)
            report.errors += 1
            return

        try:
            _, changed = await self.__sync(pair, force=False, active_only=True)
        except Exception as e:
            # A failed statement aborts the Postgres transaction: without the
            # rollback every curriculum left in the pass, and the cleanup after
            # it, would fail too.
            await self.session.rollback()
            self.logger.error(
                "failed to update timetable", curriculum_id=curriculum_id, error=str(e)
            )
            report.errors += 1
            return

        if changed:
            report.updated += 1
        else:
            report.skipped += 1

    async def __refresh_cache(
        self, curriculum_id: UUID, subjects: List[Subject], active_only: bool
    ) -> None:
        """
        Only the active set has the shape the API serves, so anything else
        invalidates the entry instead of overwriting it.
        """
        if active_only:
            await self.cache.set(curriculum_id, subjects)
        else:
            await self.cache.delete(curriculum_id)


def is_fresh(updated_at: Optional[datetime], threshold: datetime) -> bool:
    return updated_at is not None and updated_at > threshold
