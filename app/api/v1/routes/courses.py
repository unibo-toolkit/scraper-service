from fastapi import APIRouter, Query
from uuid import UUID

from app.utils.custom_logger import CustomLogger
from app.core import cache
from app.scheduler.jobs import update_courses_cache
from app.api.exceptions import NotFoundError, ServiceUnavailableError

router = APIRouter()


@router.get("/courses")
async def get_courses(
    q: str = Query(None, description="Search by title"),
    type: str = Query(None, regex="^(Bachelor|Master|SingleCycleMaster)$"),
    lang: str = Query("it", regex="^(it|en)$"),
    limit: int = Query(50, ge=1, le=300),
    offset: int = Query(0, ge=0),
):
    logger = CustomLogger("api:get_courses")
    logger.with_items(lang=lang, type=type, q=q)
    logger.info("handling get courses request")

    cached_data = await cache.get_cached_courses(logger=logger)

    if not cached_data:
        logger.info("cache miss, generating courses cache")
        await update_courses_cache(logger=logger)

        cached_data = await cache.get_cached_courses(logger=logger)
        if not cached_data:
            raise ServiceUnavailableError("Service temporarily unavailable. Please try again later.")

    courses = cached_data["items"]

    filtered = courses

    if q:
        search = q.lower()
        filtered = [
            c for c in filtered
            if search in (c.get("title_it") or "").lower()
            or search in (c.get("title_en") or "").lower()
        ]

    if type:
        filtered = [c for c in filtered if c["course_type"] == type]

    total = len(filtered)

    paginated = filtered[offset:offset + limit]

    items = []
    for course in paginated:
        curricula = course.get("curricula", [])
        sorted_curricula = sorted(curricula, key=lambda x: x.get("code", ""))

        item = {
            "id": course["id"],
            "unibo_id": course["unibo_id"],
            "title": course[f"title_{lang}"] or course["title_it"],
            "course_type": course["course_type"],
            "campus": course["campus"],
            "languages": course["languages"],
            "duration_years": course["duration_years"],
            "academic_year": course["academic_year"],
            "url": course["url"],
            "area": course["area"],
            "curricula": sorted_curricula,
        }
        items.append(item)

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/courses/{course_id}")
async def get_course_by_id(
    course_id: UUID,
    lang: str = Query("it", regex="^(it|en)$")
):
    logger = CustomLogger("api:get_course_by_id")
    logger.with_items(course_id=str(course_id), lang=lang)
    logger.debug("handling get course by id request")

    cached_data = await cache.get_cached_courses(logger=logger)

    if not cached_data:
        logger.info("cache miss, generating courses cache")
        await update_courses_cache(logger=logger)

        cached_data = await cache.get_cached_courses(logger=logger)
        if not cached_data:
            raise ServiceUnavailableError("Service temporarily unavailable. Please try again later.")

    course = None
    for c in cached_data["items"]:
        if c["id"] == str(course_id):
            course = c
            break

    if not course:
        raise NotFoundError(f"Course with ID {course_id} not found")

    curricula = course.get("curricula", [])
    sorted_curricula = sorted(curricula, key=lambda x: x.get("code", ""))

    return {
        "id": course["id"],
        "unibo_id": course["unibo_id"],
        "title": course[f"title_{lang}"] or course["title_it"],
        "course_type": course["course_type"],
        "campus": course["campus"],
        "languages": course["languages"],
        "duration_years": course["duration_years"],
        "academic_year": course["academic_year"],
        "url": course["url"],
        "area": course["area"],
        "curricula": sorted_curricula
    }
