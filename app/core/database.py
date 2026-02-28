from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, timedelta, UTC
from sqlalchemy import select, delete, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.generated import (
    Courses,
    Curricula,
    Subjects,
    TimetableEvents,
    Classrooms,
    CalendarCourses,
    CalendarLinks,
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

    async def get_curriculum_by_code(
        self,
        course_id: UUID,
        code: str,
        academic_year: int
    ) -> Optional[Curricula]:
        query = select(Curricula).where(
            Curricula.course_id == course_id,
            Curricula.code == code,
            Curricula.academic_year == academic_year
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_curriculum_by_id(self, curriculum_id: UUID) -> Optional[Curricula]:
        query = select(Curricula).where(Curricula.id == curriculum_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_subjects_by_curriculum(self, curriculum_id: UUID) -> List[Subjects]:
        query = select(Subjects).where(Subjects.curriculum_id == curriculum_id)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def bulk_insert_subjects(self, subjects: List[Dict]):
        for subject_data in subjects:
            subject = Subjects(**subject_data)
            self.session.add(subject)
        await self.session.flush()

    async def bulk_insert_timetable_events(self, events: List[Dict]):
        for event_data in events:
            event = TimetableEvents(**event_data)
            self.session.add(event)
        await self.session.flush()

    async def upsert_classroom(self, classroom_data: Dict) -> Classrooms:
        address = classroom_data.get("address")

        query = select(Classrooms).where(
            Classrooms.name == classroom_data["name"],
            Classrooms.address.is_(None)
        )
        if address:
            query = select(Classrooms).where(
                Classrooms.name == classroom_data["name"],
                Classrooms.address == address
            )

        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            if classroom_data.get("latitude") is not None:
                existing.latitude = classroom_data["latitude"]
            if classroom_data.get("longitude") is not None:
                existing.longitude = classroom_data["longitude"]
            await self.session.flush()
            return existing

        classroom = Classrooms(**classroom_data)
        self.session.add(classroom)
        await self.session.flush()
        return classroom

    async def get_active_curricula(self) -> List[Curricula]:
        threshold_date = datetime.now(UTC) - timedelta(days=7)

        query = (
            select(Curricula)
            .join(CalendarCourses)
            .join(CalendarLinks)
            .where(
                and_(
                    CalendarLinks.ttl_expires_at > datetime.now(UTC),
                    CalendarLinks.last_accessed_at > threshold_date
                )
            )
            .options(selectinload(Curricula.course))
            .distinct()
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def delete_subjects_by_curriculum(self, curriculum_id: UUID):
        await self.session.execute(
            delete(Subjects).where(Subjects.curriculum_id == curriculum_id)
        )
        await self.session.flush()

    async def delete_timetable_events_by_subject(self, subject_ids: List[UUID]):
        if not subject_ids:
            return

        await self.session.execute(
            delete(TimetableEvents).where(TimetableEvents.subject_id.in_(subject_ids))
        )
        await self.session.flush()

    async def update_course_timetable_hash(
        self,
        course_id: UUID,
        timetable_hash: str
    ):
        stmt = (
            update(Courses)
            .where(Courses.id == course_id)
            .values(
                timetable_hash=timetable_hash,
                timetable_updated_at=datetime.now(UTC)
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def cleanup_unused_classrooms(self):
        subquery = select(TimetableEvents.classroom_id).where(
            TimetableEvents.classroom_id.is_not(None)
        ).distinct()

        stmt = delete(Classrooms).where(
            Classrooms.id.not_in(subquery)
        )

        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def delete_obsolete_courses(self, current_unibo_ids: List[int]):
        if not current_unibo_ids:
            return 0

        stmt = delete(Courses).where(
            Courses.unibo_id.not_in(current_unibo_ids)
        )

        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def get_course_by_curriculum(self, curriculum_id: UUID) -> Optional[Courses]:
        query = (
            select(Courses)
            .join(Curricula)
            .where(Curricula.id == curriculum_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
