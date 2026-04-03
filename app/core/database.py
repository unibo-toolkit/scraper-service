from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, timedelta, UTC
from sqlalchemy import select, delete, update, and_, or_
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
    CalendarEvents,
)
from app.utils.custom_logger import CustomLogger


class DatabaseOperations:

    def __init__(self, session: AsyncSession, logger: Optional[CustomLogger] = None):
        self.session = session
        self.logger = logger or CustomLogger("database")

    async def get_all_courses(self, with_curricula: bool = False, active_only: bool = True) -> List[Courses]:
        query = select(Courses)
        if active_only:
            query = query.where(Courses.is_active == True)
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
            update_data["is_active"] = True

            stmt = update(Courses).where(Courses.id == existing.id).values(**update_data)
            await self.session.execute(stmt)
            await self.session.flush()
            self.logger.info("updated course", unibo_id=course_data["unibo_id"])

            return existing

        course_data_clean = {k: v for k, v in course_data.items() if k != "curricula"}
        course_data_clean["is_active"] = True
        course = Courses(**course_data_clean)
        self.session.add(course)
        await self.session.flush()
        self.logger.info("created new course", unibo_id=course_data["unibo_id"])
        return course

    async def upsert_curricula(self, course_id: UUID, curricula_list: List[Dict]):
        for curriculum_data in curricula_list:
            existing = await self.get_curriculum_by_code(
                course_id,
                curriculum_data["code"],
                curriculum_data["academic_year"]
            )

            if existing:
                stmt = update(Curricula).where(Curricula.id == existing.id).values(
                    label=curriculum_data["label"],
                    is_active=True
                )
                await self.session.execute(stmt)
            else:
                curriculum = Curricula(
                    course_id=course_id,
                    code=curriculum_data["code"],
                    label=curriculum_data["label"],
                    academic_year=curriculum_data["academic_year"],
                    is_active=True
                )
                self.session.add(curriculum)

        await self.session.flush()

    async def mark_inactive_curricula(
        self,
        course_id: UUID,
        active_codes: List[tuple]
    ):
        if not active_codes:
            return

        from sqlalchemy import tuple_
        stmt = (
            update(Curricula)
            .where(
                and_(
                    Curricula.course_id == course_id,
                    Curricula.is_active == True,
                    ~tuple_(Curricula.code, Curricula.academic_year).in_(active_codes)
                )
            )
            .values(is_active=False)
        )
        await self.session.execute(stmt)
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

    async def get_subjects_by_curriculum(self, curriculum_id: UUID, active_only: bool = True) -> List[Subjects]:
        query = select(Subjects).where(Subjects.curriculum_id == curriculum_id)
        if active_only:
            query = query.where(Subjects.is_active == True)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_subject_by_key(
        self,
        curriculum_id: UUID,
        title: str,
        module_code: Optional[str],
        professor: Optional[str]
    ) -> Optional[Subjects]:
        query = select(Subjects).where(
            and_(
                Subjects.curriculum_id == curriculum_id,
                Subjects.title == title,
                Subjects.module_code == module_code if module_code else Subjects.module_code.is_(None),
                Subjects.professor == professor if professor else Subjects.professor.is_(None)
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def upsert_subjects(self, subjects: List[Dict]):
        for subject_data in subjects:
            existing = await self.get_subject_by_key(
                subject_data["curriculum_id"],
                subject_data["title"],
                subject_data.get("module_code"),
                subject_data.get("professor")
            )

            if existing:
                stmt = update(Subjects).where(Subjects.id == existing.id).values(
                    credits=subject_data.get("credits"),
                    group_id=subject_data.get("group_id"),
                    is_active=True,
                    updated_at=datetime.now(UTC)
                )
                await self.session.execute(stmt)
            else:
                subject_data["is_active"] = True
                subject = Subjects(**subject_data)
                self.session.add(subject)

        await self.session.flush()

    async def mark_inactive_subjects(
        self,
        curriculum_id: UUID,
        active_keys: List[tuple]
    ):
        if not active_keys:
            return

        conditions = []
        for title, module_code, professor in active_keys:
            cond = and_(
                Subjects.title == title,
                Subjects.module_code == module_code if module_code else Subjects.module_code.is_(None),
                Subjects.professor == professor if professor else Subjects.professor.is_(None)
            )
            conditions.append(cond)

        if not conditions:
            return

        stmt = (
            update(Subjects)
            .where(
                and_(
                    Subjects.curriculum_id == curriculum_id,
                    Subjects.is_active == True,
                    ~or_(*conditions),
                )
            )
            .values(is_active=False)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def sync_timetable_events(self, subject_ids: List[UUID], events: List[Dict]):
        from sqlalchemy.dialects.postgresql import insert

        new_hashes = {e["content_hash"] for e in events}
        calendar_subq = select(CalendarEvents.timetable_event_id).distinct()

        delete_conditions = [
            TimetableEvents.subject_id.in_(subject_ids),
            TimetableEvents.id.not_in(calendar_subq),
        ]
        if new_hashes:
            delete_conditions.append(TimetableEvents.content_hash.not_in(new_hashes))

        await self.session.execute(delete(TimetableEvents).where(and_(*delete_conditions)))
        await self.session.flush()

        if events:
            stmt = insert(TimetableEvents).values(events)
            stmt = stmt.on_conflict_do_nothing(constraint='timetable_events_unique_event')
            await self.session.execute(stmt)
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
        now = datetime.now(UTC)
        threshold_date = now - timedelta(days=7)

        query = (
            select(Curricula)
            .join(CalendarCourses)
            .join(CalendarLinks)
            .where(
                and_(
                    CalendarLinks.ttl_expires_at > now,
                    CalendarLinks.last_accessed_at > threshold_date
                )
            )
            .options(selectinload(Curricula.course))
            .distinct()
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_curriculum_timetable_hash(
        self,
        curriculum_id: UUID,
        timetable_hash: str
    ):
        stmt = (
            update(Curricula)
            .where(Curricula.id == curriculum_id)
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

    async def mark_inactive_courses(self, active_unibo_ids: List[int]):
        if not active_unibo_ids:
            return 0

        stmt = (
            update(Courses)
            .where(
                and_(
                    Courses.is_active == True,
                    Courses.unibo_id.not_in(active_unibo_ids)
                )
            )
            .values(is_active=False)
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

    async def get_timetable_events_by_subject_ids(
        self,
        subject_ids: List[UUID],
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[TimetableEvents]:
        conditions = [TimetableEvents.subject_id.in_(subject_ids)]

        if from_date is not None:
            conditions.append(TimetableEvents.start_datetime >= from_date)
        if to_date is not None:
            conditions.append(TimetableEvents.start_datetime < to_date)

        query = (
            select(TimetableEvents)
            .where(and_(*conditions))
            .options(selectinload(TimetableEvents.classroom))
            .order_by(TimetableEvents.start_datetime)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_curricula_by_subject_ids(self, subject_ids: List[UUID]) -> List[Curricula]:
        query = (
            select(Curricula)
            .join(Subjects, Subjects.curriculum_id == Curricula.id)
            .where(Subjects.id.in_(subject_ids))
            .options(selectinload(Curricula.course))
            .distinct()
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def cleanup_stale_events(self, stale_threshold: datetime) -> int:
        calendar_events_subq = select(CalendarEvents.timetable_event_id).distinct()

        stale_curricula_subq = (
            select(Curricula.id)
            .where(
                or_(
                    Curricula.timetable_updated_at.is_(None),
                    Curricula.timetable_updated_at < stale_threshold,
                )
            )
        )

        stale_subjects_subq = (
            select(Subjects.id)
            .where(Subjects.curriculum_id.in_(stale_curricula_subq))
        )

        stmt = delete(TimetableEvents).where(
            and_(
                TimetableEvents.id.not_in(calendar_events_subq),
                TimetableEvents.subject_id.in_(stale_subjects_subq),
            )
        )

        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def get_subject_by_id(self, subject_id: UUID) -> Optional[Subjects]:
        query = (
            select(Subjects)
            .where(Subjects.id == subject_id)
            .options(selectinload(Subjects.curriculum))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
