from typing import List, Optional, Sequence
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.core.database.base import Operations
from app.models.courses import Course, Curriculum
from app.models.generated import Courses

UNIBO_ID_CONSTRAINT = "courses_unibo_id_key"


class CoursesOperations(Operations):
    async def list_all(self, active_only: bool = True) -> List[Course]:
        query = select(Courses).options(selectinload(Courses.curricula))
        if active_only:
            query = query.where(Courses.is_active.is_(True))

        rows = (await self.session.execute(query)).scalars().all()
        return [to_course(row) for row in rows]

    async def get(self, course_id: UUID) -> Optional[Course]:
        query = (
            select(Courses)
            .where(Courses.id == course_id)
            .options(selectinload(Courses.curricula))
        )
        row = (await self.session.execute(query)).scalar_one_or_none()
        return to_course(row) if row else None

    async def upsert(self, course: Course) -> UUID:
        stmt = insert(Courses).values(
            unibo_id=course.unibo_id,
            title_it=course.title_it,
            title_en=course.title_en,
            course_type=course.course_type,
            campus=course.campus,
            languages=list(course.languages),
            duration_years=course.duration_years,
            url=course.url,
            area=course.area,
            is_active=True,
        )
        stmt = stmt.on_conflict_do_update(
            constraint=UNIBO_ID_CONSTRAINT,
            set_={
                "title_it": stmt.excluded.title_it,
                "title_en": stmt.excluded.title_en,
                "course_type": stmt.excluded.course_type,
                "campus": stmt.excluded.campus,
                "languages": stmt.excluded.languages,
                "duration_years": stmt.excluded.duration_years,
                "url": stmt.excluded.url,
                "area": stmt.excluded.area,
                "is_active": True,
            },
        ).returning(Courses.id)

        course_id = (await self.session.execute(stmt)).scalar_one()
        await self.session.flush()
        return course_id

    async def deactivate_missing(self, active_unibo_ids: Sequence[int]) -> int:
        if not active_unibo_ids:
            return 0

        stmt = (
            update(Courses)
            .where(Courses.is_active.is_(True), Courses.unibo_id.not_in(active_unibo_ids))
            .values(is_active=False)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount


def to_course(row: Courses, with_curricula: bool = True) -> Course:
    curricula = (
        tuple(
            Curriculum(
                id=curr.id,
                code=curr.code,
                label=curr.label,
                academic_year=curr.academic_year,
            )
            for curr in row.curricula
            if curr.is_active
        )
        if with_curricula
        else ()
    )

    return Course(
        id=row.id,
        unibo_id=row.unibo_id,
        title_it=row.title_it,
        title_en=row.title_en,
        course_type=row.course_type,
        campus=row.campus,
        languages=tuple(row.languages or ()),
        duration_years=row.duration_years,
        url=row.url,
        area=row.area,
        curricula=curricula,
    )
