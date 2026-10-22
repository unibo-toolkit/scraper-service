from dataclasses import replace
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Set
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.core.database.base import Operations
from app.models.generated import (
    CalendarCourses,
    CalendarLinks,
    Curricula,
    Subjects,
    TimetableEvents,
)
from app.models.timetable import Classroom, ClassroomKey, Event, SubjectKey

UNIQUE_EVENT_CONSTRAINT = "timetable_events_unique_event"

# Columns a scrape may change without moving the row identity: the unique
# constraint only covers subject_id, start, end and content_hash, and
# content_hash itself is built on a subset of the fields.
MUTABLE_COLUMNS = (
    "classroom_id",
    "teams_link",
    "notes",
    "module_code",
    "credits",
    "group_id",
    "family_hash",
)


class EventsOperations(Operations):
    async def list_by_subjects(
        self,
        subject_ids: Sequence[UUID],
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[Event]:
        query = (
            select(TimetableEvents)
            .where(TimetableEvents.subject_id.in_(subject_ids))
            .options(selectinload(TimetableEvents.classroom))
            .order_by(TimetableEvents.start_datetime)
        )
        if from_date is not None:
            query = query.where(TimetableEvents.start_datetime >= from_date)
        if to_date is not None:
            query = query.where(TimetableEvents.start_datetime < to_date)

        rows = (await self.session.execute(query)).scalars().all()
        return [_to_event(row) for row in rows]

    async def sync(
        self,
        subject_ids: Sequence[UUID],
        events: Sequence[Event],
        subjects: Dict[SubjectKey, UUID],
        classrooms: Dict[ClassroomKey, UUID],
    ) -> None:
        """
        Replaces the events of the given subjects with the scraped ones.

        Rows are identified by content_hash, so an event that did not change
        keeps its id. The columns outside that identity, the classroom above
        all, are refreshed in place: they would otherwise stay as first
        scraped forever.
        """
        resolved = [
            replace(event, subject_id=subjects[event.subject_key])
            for event in events
            if event.subject_key in subjects
        ]

        payload = self.__deduplicate(self.__payload(event, classrooms) for event in resolved)

        await self.__delete_missing(subject_ids, {row["content_hash"] for row in payload})

        if payload:
            stmt = insert(TimetableEvents).values(payload)
            await self.session.execute(
                stmt.on_conflict_do_update(
                    constraint=UNIQUE_EVENT_CONSTRAINT,
                    set_={column: stmt.excluded[column] for column in MUTABLE_COLUMNS},
                    # Without it every pass would touch every row and fire the
                    # updated_at trigger for nothing.
                    where=or_(
                        *(
                            TimetableEvents.__table__.c[column].is_distinct_from(
                                stmt.excluded[column]
                            )
                            for column in MUTABLE_COLUMNS
                        )
                    ),
                )
            )
            await self.session.flush()

    @staticmethod
    def __deduplicate(payload: Iterable[dict]) -> List[dict]:
        """
        Drops rows repeating a conflict target, which ON CONFLICT DO UPDATE
        refuses to touch twice in one statement.

        Returns:
            One row per (subject_id, start, end, content_hash), first wins.
        """
        unique: Dict[tuple, dict] = {}
        for row in payload:
            key = (
                row["subject_id"],
                row["start_datetime"],
                row["end_datetime"],
                row["content_hash"],
            )
            unique.setdefault(key, row)
        return list(unique.values())

    async def __delete_missing(
        self, subject_ids: Sequence[UUID], keep_hashes: Set[str]
    ) -> None:
        stmt = delete(TimetableEvents).where(TimetableEvents.subject_id.in_(subject_ids))
        if keep_hashes:
            stmt = stmt.where(TimetableEvents.content_hash.not_in(keep_hashes))

        await self.session.execute(stmt)
        await self.session.flush()

    @staticmethod
    def __payload(
        event: Event,
        classrooms: Dict[ClassroomKey, UUID],
    ) -> dict:
        return {
            "subject_id": event.subject_id,
            "title": event.title,
            "start_datetime": event.start,
            "end_datetime": event.end,
            "professor": event.professor,
            "classroom_id": classrooms.get(event.classroom.key) if event.classroom else None,
            "teams_link": event.teams_link,
            "is_remote": event.is_remote,
            "notes": event.notes,
            "module_code": event.module_code,
            "credits": event.credits,
            "group_id": event.group_id,
            "content_hash": event.content_hash,
            "family_hash": event.family_hash,
        }

    async def cleanup_stale(self, stale_before: datetime, protected_after: datetime) -> int:
        """
        Drops events of curricula that stopped being refreshed, unless a live
        calendar still points at them.
        """
        stale_curricula = select(Curricula.id).where(
            or_(
                Curricula.timetable_updated_at.is_(None),
                Curricula.timetable_updated_at < stale_before,
            )
        )
        protected_curricula = (
            select(CalendarCourses.curriculum_id)
            .join(CalendarLinks, CalendarLinks.id == CalendarCourses.calendar_id)
            .where(CalendarLinks.ttl_expires_at > protected_after)
            .distinct()
        )
        stale_subjects = select(Subjects.id).where(
            Subjects.curriculum_id.in_(stale_curricula),
            Subjects.curriculum_id.not_in(protected_curricula),
        )

        result = await self.session.execute(
            delete(TimetableEvents).where(TimetableEvents.subject_id.in_(stale_subjects))
        )
        await self.session.flush()
        return result.rowcount


def _to_event(row: TimetableEvents) -> Event:
    classroom = row.classroom
    return Event(
        id=row.id,
        subject_id=row.subject_id,
        title=row.title,
        start=row.start_datetime,
        end=row.end_datetime,
        professor=row.professor,
        module_code=row.module_code,
        credits=row.credits,
        group_id=row.group_id,
        is_remote=row.is_remote,
        teams_link=row.teams_link,
        notes=row.notes,
        location=classroom.name if classroom else None,
        classroom=Classroom(
            id=classroom.id,
            name=classroom.name,
            address=classroom.address,
            latitude=classroom.latitude,
            longitude=classroom.longitude,
        )
        if classroom
        else None,
    )
