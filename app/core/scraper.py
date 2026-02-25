import asyncio
from typing import List, Dict, Optional
from unibo_toolkit import CourseScraper, HTTPClient, BaseCourse
from unibo_toolkit.scrapers import TimetableScraper
from unibo_toolkit.enums import Language
from unibo_toolkit.models import Curriculum

from app.utils.custom_logger import CustomLogger


async def _fetch_sites_urls(course: BaseCourse, client: HTTPClient, logger: Optional[CustomLogger] = None):
    if not logger:
        logger = CustomLogger("scraper:fetch_sites")

    for attempt in range(3):
        try:
            await course.fetch_site_url(client)
            return
        except ValueError as e:
            logger.warning("failed to fetch site url", course_id=course.course_id, attempt=attempt + 1, error=str(e))

    logger.error("failed to fetch site url after retries", course_id=course.course_id, retries=3)


def _get_course_dict(course: BaseCourse) -> Dict:
    return {
        "unibo_id": course.course_id,
        "title_it": course.title,
        "title_en": None,
        "course_type": _map_course_type(course.get_course_type().value),
        "campus": course.campus.value if course.campus else None,
        "languages": [lang.value for lang in course.languages] if course.languages else [],
        "duration_years": course.duration_years,
        "academic_year": str(course.year),
        "url": course.course_site_url,
        "area": _extract_area(course.area),
        "curricula": (
            [
                {"code": curr.code, "label": curr.label}
                for curr in (course.get_available_curricula() or [])
            ]
            if course.get_available_curricula()
            else []
        ),
    }


async def fetch_courses_italian(logger: Optional[CustomLogger] = None) -> List[Dict]:
    if not logger:
        logger = CustomLogger("scraper:courses_italian")

    logger.info("fetching courses in italian")

    async with CourseScraper() as scraper:
        courses = await scraper.get_all_courses(language=Language.IT)

    logger.info("fetch site URLs for courses", count=len(courses))
    async with HTTPClient() as client:
        tasks = [asyncio.create_task(_fetch_sites_urls(course, client, logger)) for course in courses]
        await asyncio.gather(*tasks)

    logger.info("fetch available curricula for courses")

    tasks = [asyncio.create_task(course.fetch_available_curricula()) for course in courses]
    await asyncio.gather(*tasks)

    result = []
    for course in courses:
        result.append(_get_course_dict(course))

    logger.info("fetched courses in italian", count=len(result))
    return result


async def fetch_courses_english(logger: Optional[CustomLogger] = None) -> Dict[int, str]:
    if not logger:
        logger = CustomLogger("scraper:courses_english")

    logger.info("fetching courses in english")

    async with CourseScraper() as scraper:
        courses = await scraper.get_all_courses(language=Language.EN)

    mapping = {}
    for course in courses:
        mapping[course.course_id] = course.title

    logger.info("fetched english titles", count=len(mapping))
    return mapping


async def fetch_timetable(
    course_site_url: str, curriculum_code: str, curriculum_label: str, academic_year: int
) -> Dict:
    logger.info("fetching timetable", curriculum_code=curriculum_code, year=academic_year)

    curriculum = Curriculum(code=curriculum_code, label=curriculum_label)

    async with TimetableScraper() as scraper:
        timetable = await scraper.get_curriculum_timetable(
            course_site_url=course_site_url, curriculum=curriculum, academic_year=academic_year
        )

    return {
        "events": [_parse_event(e) for e in timetable.events],
        "content_hash": timetable.content_hash,
    }


def _map_course_type(course_type: str) -> str:
    mapping = {
        "bachelor": "Bachelor",
        "master": "Master",
        "combined_bachelor_master": "SingleCycleMaster",
        "single_cycle": "SingleCycleMaster",
        "single_cycle_master": "SingleCycleMaster",
    }
    return mapping.get(course_type, "Master")


def _extract_area(area) -> str:
    if not area:
        return None

    if hasattr(area, 'value'):
        if isinstance(area.value, tuple) and len(area.value) > 1:
            return area.value[1]
        return area.value

    return str(area)


def _parse_event(event) -> Dict:
    return {
        "title": event.title,
        "start_time": event.start.isoformat(),
        "end_time": event.end.isoformat(),
        "location": event.location,
        "professor": event.professor,
        "event_type": event.event_type.value if event.event_type else None,
        "cfu": event.cfu,
    }
