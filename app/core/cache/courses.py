from datetime import UTC, datetime
from typing import List, Optional
from uuid import UUID

from app import config
from app.core.cache.base import JsonCache
from app.models.courses import Course, Curriculum

KEY = "courses:full"


class CoursesCache(JsonCache):
    async def get(self) -> Optional[List[Course]]:
        payload = await super().get(KEY)
        if not payload:
            self.logger.info("cache miss for courses")
            return None

        self.logger.info("cache hit for courses")
        return [_to_course(item) for item in payload["items"]]

    async def set(self, courses: List[Course]) -> None:
        ttl = config.scraper.cache_courses_list_ttl
        payload = {
            "items": [_to_payload(course) for course in courses],
            "cached_at": datetime.now(UTC).isoformat(),
            "ttl": ttl,
        }

        await super().set(KEY, payload, ttl)
        self.logger.info("cached courses", count=len(courses))


def _to_payload(course: Course) -> dict:
    return {
        "id": str(course.id),
        "unibo_id": course.unibo_id,
        "title_it": course.title_it,
        "title_en": course.title_en,
        "course_type": course.course_type,
        "campus": course.campus,
        "languages": list(course.languages),
        "duration_years": course.duration_years,
        "url": course.url,
        "area": course.area,
        "curricula": sorted(
            (
                {
                    "id": str(curr.id),
                    "code": curr.code,
                    "label": curr.label,
                    "academic_year": curr.academic_year,
                }
                for curr in course.curricula
            ),
            key=lambda curr: (curr["academic_year"], curr["code"]),
        ),
    }


def _to_course(payload: dict) -> Course:
    return Course(
        id=UUID(payload["id"]),
        unibo_id=payload["unibo_id"],
        title_it=payload["title_it"],
        title_en=payload["title_en"],
        course_type=payload["course_type"],
        campus=payload["campus"],
        languages=tuple(payload["languages"] or ()),
        duration_years=payload["duration_years"],
        url=payload["url"],
        area=payload["area"],
        curricula=tuple(
            Curriculum(
                id=UUID(curr["id"]),
                code=curr["code"],
                label=curr["label"],
                academic_year=curr["academic_year"],
            )
            for curr in payload["curricula"]
        ),
    )
