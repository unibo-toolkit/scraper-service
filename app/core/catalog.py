from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CoursesCache
from app.core.database import CoursesOperations, CurriculaOperations
from app.core.scraper import CoursesScraper
from app.models.courses import Course
from app.utils.custom_logger import CustomLogger


@dataclass(frozen=True, slots=True)
class CoursePage:
    """
    One page of a course listing.

    Attributes:
        items: Courses of the requested slice, already filtered.
        total: How many courses matched the filters before slicing, which is
            what the client needs to paginate.
    """

    items: List[Course]
    total: int


class CourseCatalog:
    """
    Read model of the course catalogue: served from Redis, rebuilt from the
    scraper on demand or by the scheduler.
    """

    def __init__(self, session: AsyncSession, logger: CustomLogger):
        self.session = session
        self.logger = logger
        self.courses = CoursesOperations(session, logger)
        self.curricula = CurriculaOperations(session, logger)
        self.cache = CoursesCache(logger)
        self.scraper = CoursesScraper(logger)

    async def refresh(self) -> List[Course]:
        scraped = await self.scraper.fetch()

        for course in scraped:
            course_id = await self.courses.upsert(course)
            await self.__save_curricula(course_id, course)

        deactivated = await self.courses.deactivate_missing([c.unibo_id for c in scraped])
        if deactivated:
            self.logger.info("marked inactive courses", count=deactivated)

        await self.session.commit()

        courses = await self.courses.list_all()
        await self.cache.set(courses)
        return courses

    async def search(
        self,
        query: Optional[str] = None,
        course_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> CoursePage:
        courses = await self.__cached()

        if query:
            needle = query.lower()
            courses = [c for c in courses if needle in c.title_it.lower() or needle in (c.title_en or "").lower()]
        if course_type:
            courses = [c for c in courses if c.course_type == course_type]

        return CoursePage(items=courses[offset : offset + limit], total=len(courses))

    async def get(self, course_id: UUID) -> Optional[Course]:
        return next((c for c in await self.__cached() if c.id == course_id), None)

    async def __cached(self) -> List[Course]:
        cached = await self.cache.get()
        if cached is not None:
            return cached

        self.logger.info("cache miss, rebuilding courses cache")
        return await self.refresh()

    async def __save_curricula(self, course_id: UUID, course: Course) -> None:
        curricula = course.expand_curricula()
        if not curricula:
            return

        await self.curricula.upsert_many(course_id, curricula)
        await self.curricula.deactivate_missing(course_id, [curr.key for curr in curricula])
