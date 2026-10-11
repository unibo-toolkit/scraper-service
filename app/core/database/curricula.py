from datetime import UTC, datetime
from typing import List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.core.database.base import Operations
from app.core.database.courses import to_course
from app.models.courses import CourseCurriculum, Curriculum
from app.models.generated import (
    CalendarCourses,
    CalendarLinks,
    Curricula,
    Subjects,
    TimetableEvents,
)

CODE_CONSTRAINT = "curricula_course_id_code_academic_year_key"


class CurriculaOperations(Operations):
    async def get(self, curriculum_id: UUID) -> Optional[CourseCurriculum]:
        query = self.__with_course().where(Curricula.id == curriculum_id)
        row = (await self.session.execute(query)).scalar_one_or_none()
        return _to_pair(row) if row else None

    async def list_subscribed(self) -> List[CourseCurriculum]:
        """
        Curricula referenced by a calendar that has not expired yet.
        """
        query = (
            self.__with_course()
            .join(CalendarCourses)
            .join(CalendarLinks)
            .where(CalendarLinks.ttl_expires_at > datetime.now(UTC))
            .distinct()
        )
        rows = (await self.session.execute(query)).scalars().all()
        return [_to_pair(row) for row in rows]

    async def list_by_subjects(self, subject_ids: Sequence[UUID]) -> List[CourseCurriculum]:
        query = (
            self.__with_course()
            .join(Subjects, Subjects.curriculum_id == Curricula.id)
            .where(Subjects.id.in_(subject_ids))
            .distinct()
        )
        rows = (await self.session.execute(query)).scalars().all()
        return [_to_pair(row) for row in rows]

    @staticmethod
    def __with_course():
        return select(Curricula).options(selectinload(Curricula.course))

    async def upsert_many(self, course_id: UUID, curricula: Sequence[Curriculum]) -> None:
        if not curricula:
            return

        stmt = insert(Curricula).values(
            [
                {
                    "course_id": course_id,
                    "code": curr.code,
                    "label": curr.label,
                    "academic_year": curr.academic_year,
                    "is_active": True,
                }
                for curr in curricula
            ]
        )
        stmt = stmt.on_conflict_do_update(
            constraint=CODE_CONSTRAINT,
            set_={"label": stmt.excluded.label, "is_active": True},
        )

        await self.session.execute(stmt)
        await self.session.flush()

    async def deactivate_missing(
        self, course_id: UUID, active_keys: Sequence[Tuple[str, int]]
    ) -> None:
        if not active_keys:
            return

        stmt = (
            update(Curricula)
            .where(
                Curricula.course_id == course_id,
                Curricula.is_active.is_(True),
                ~tuple_(Curricula.code, Curricula.academic_year).in_(active_keys),
            )
            .values(is_active=False)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def touch_timetable(self, curriculum_id: UUID, content_hash: str) -> None:
        stmt = (
            update(Curricula)
            .where(Curricula.id == curriculum_id)
            .values(timetable_hash=content_hash, timetable_updated_at=datetime.now(UTC))
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def has_events(self, curriculum_id: UUID) -> bool:
        subjects = select(Subjects.id).where(Subjects.curriculum_id == curriculum_id)
        query = select(TimetableEvents.id).where(TimetableEvents.subject_id.in_(subjects)).limit(1)
        return (await self.session.execute(query)).scalar_one_or_none() is not None


def _to_pair(row: Curricula) -> CourseCurriculum:
    return CourseCurriculum(
        course=to_course(row.course, with_curricula=False),
        curriculum=Curriculum(
            id=row.id,
            code=row.code,
            label=row.label,
            academic_year=row.academic_year,
            timetable_hash=row.timetable_hash,
            timetable_updated_at=row.timetable_updated_at,
        ),
    )
