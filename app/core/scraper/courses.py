import asyncio
from typing import AsyncIterator, Dict, List, Sequence, Tuple

from unibo_toolkit import BaseCourse, CourseScraper, HTTPClient
from unibo_toolkit.enums import Language
from unibo_toolkit.models import Curriculum as UniBoCurriculum

from app import config
from app.core.scraper.mapper import to_course
from app.models.courses import Course
from app.utils.custom_logger import CustomLogger

SITE_URL_RETRIES = 3


class CoursesScraper:
    def __init__(self, logger: CustomLogger):
        self.logger = logger

    async def fetch(self) -> List[Course]:
        """
        Italian catalogue enriched with site urls, curricula and english titles.

        Everything runs on one HTTP client: the site throttles a burst of fresh
        connections, and a per-course client made every request pay for its own
        TLS handshake.
        """
        async with HTTPClient(timeout=config.scraper.request_timeout) as client:
            async with CourseScraper(http_client=client) as scraper:
                courses = await scraper.get_all_courses(language=Language.IT)
                self.logger.info("fetched courses", count=len(courses))

                await self.__fetch_site_urls(courses, client)
                curricula = await self.__fetch_curricula(courses, scraper)
                titles_en = await self.__fetch_english_titles(scraper)

        return [
            to_course(course, titles_en.get(course.course_id), curricula.get(course.course_id, ()))
            for course in courses
        ]

    async def __fetch_site_urls(self, courses: Sequence[BaseCourse], client: HTTPClient) -> None:
        self.logger.info("fetching site urls", count=len(courses))
        delay = config.scraper.delay_between_site_url_requests

        async for course in _throttled(courses, delay):
            await self.__fetch_site_url(course, client)

    async def __fetch_site_url(self, course: BaseCourse, client: HTTPClient) -> None:
        for attempt in range(SITE_URL_RETRIES):
            try:
                await course.fetch_site_url(client)
                return
            except ValueError as e:
                self.logger.warning(
                    "failed to fetch site url",
                    course_id=course.course_id,
                    attempt=attempt + 1,
                    error=str(e),
                )

        self.logger.error(
            "failed to fetch site url after retries",
            course_id=course.course_id,
            retries=SITE_URL_RETRIES,
        )

    async def __fetch_curricula(
        self, courses: Sequence[BaseCourse], scraper: CourseScraper
    ) -> Dict[int, Tuple[UniBoCurriculum, ...]]:
        """
        Curricula per course id.

        A course whose site url never resolved cannot be queried, and one that
        fails comes back empty: unibo_toolkit swallows the error and returns an
        empty list, which is indistinguishable from a course that genuinely has
        no curricula. Callers must treat empty as "unknown", never as "none".
        """
        self.logger.info("fetching curricula", count=len(courses))
        delay = config.scraper.delay_between_curricula_requests
        found: Dict[int, Tuple[UniBoCurriculum, ...]] = {}

        async for course in _throttled(courses, delay):
            if not course.course_site_url:
                continue

            curricula = await scraper.get_available_curricula(course.course_site_url)
            if curricula:
                found[course.course_id] = tuple(curricula)

        self.logger.info("fetched curricula", courses_with_curricula=len(found))
        return found

    async def __fetch_english_titles(self, scraper: CourseScraper) -> Dict[int, str]:
        courses = await scraper.get_all_courses(language=Language.EN)
        self.logger.info("fetched english titles", count=len(courses))
        return {course.course_id: course.title for course in courses}


async def _throttled(items: Sequence[BaseCourse], delay: float) -> AsyncIterator[BaseCourse]:
    """
    Sleeps between items, but not after the last one.
    """
    last = len(items) - 1
    for index, item in enumerate(items):
        yield item
        if index < last:
            await asyncio.sleep(delay)
