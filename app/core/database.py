from typing import List, Optional, Dict
from uuid import UUID
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.generated import (
    Courses,
    Curricula,
)
from app.utils.custom_logger import CustomLogger


class DatabaseOperations:

    def __init__(self, session: AsyncSession, logger: Optional[CustomLogger] = None):
        self.session = session
        self.logger = logger or CustomLogger("database")

    async def get_all_courses(self, with_curricula: bool = False) -> List[Courses]:
        query = select(Courses)
        if with_curricula:
            query = query.options(selectinload(Courses.curricula))

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_course_by_id(self, course_id: UUID) -> Optional[Courses]:
        query = select(Courses).where(Courses.id == course_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_course_by_unibo_id(self, unibo_id: int) -> Optional[Courses]:
        query = select(Courses).where(Courses.unibo_id == unibo_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def upsert_course(self, course_data: Dict) -> Courses:
        existing = await self.get_course_by_unibo_id(course_data["unibo_id"])

        if existing:
            update_data = {k: v for k, v in course_data.items() if k != "curricula"}

            stmt = update(Courses).where(Courses.id == existing.id).values(**update_data)
            await self.session.execute(stmt)
            await self.session.flush()
            self.logger.debug("updated course", unibo_id=course_data["unibo_id"])

            return existing

        course_data_clean = {k: v for k, v in course_data.items() if k != "curricula"}
        course = Courses(**course_data_clean)
        self.session.add(course)
        await self.session.flush()
        self.logger.debug("created new course", unibo_id=course_data["unibo_id"])
        return course

    async def update_course_titles(self, unibo_id: int, title_it: str = None, title_en: str = None):
        stmt = update(Courses).where(Courses.unibo_id == unibo_id)

        values = {}
        if title_it:
            values["title_it"] = title_it
        if title_en:
            values["title_en"] = title_en

        if values:
            stmt = stmt.values(**values)
            await self.session.execute(stmt)
            await self.session.flush()

    async def get_curricula_by_course(self, course_id: UUID) -> List[Curricula]:
        query = select(Curricula).where(Curricula.course_id == course_id)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def delete_curricula_by_course(self, course_id: UUID):
        await self.session.execute(delete(Curricula).where(Curricula.course_id == course_id))

    async def insert_curricula(self, course_id: UUID, curricula_list: List[Dict]):
        await self.delete_curricula_by_course(course_id)

        for curriculum_data in curricula_list:
            curriculum = Curricula(
                course_id=course_id,
                code=curriculum_data["code"],
                label=curriculum_data["label"],
                academic_year=curriculum_data["academic_year"],
            )
            self.session.add(curriculum)

        await self.session.flush()
