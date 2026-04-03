from fastapi import APIRouter, Query, Depends
from uuid import UUID
from datetime import datetime, timedelta, UTC
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.custom_logger import CustomLogger
from app.utils.database import get_db
from app.core import cache
from app.core.subjects import fetch_and_save_subjects
from app.core.database import DatabaseOperations
from app.api.exceptions import NotFoundError
from app import config

router = APIRouter()


@router.get("/courses/{course_id}/subjects")
async def get_course_subjects(
    course_id: UUID,
    curriculum_id: UUID = Query(..., description="Curriculum UUID"),
    include_inactive: bool = Query(False, description="Include inactive subjects"),
    session: AsyncSession = Depends(get_db)
):
    logger = CustomLogger("api:get_course_subjects")

    db_ops = DatabaseOperations(session, logger)

    course = await db_ops.get_course_by_id(course_id)
    if not course:
        raise NotFoundError(f"Course {course_id} not found")

    curriculum = await db_ops.get_curriculum_by_id(curriculum_id)
    if not curriculum:
        raise NotFoundError(f"Curriculum {curriculum_id} not found")

    if curriculum.course_id != course.id:
        raise NotFoundError(f"Curriculum {curriculum_id} does not belong to course {course_id}")

    cache_key = f"subjects:{curriculum.id}"
    if not include_inactive:
        refresh_threshold = datetime.now(UTC) - timedelta(seconds=config.scraper.subjects_refresh_ttl)
        is_stale = (
            curriculum.timetable_updated_at is None
            or curriculum.timetable_updated_at <= refresh_threshold
        )
        if not is_stale:
            cached = await cache.get_cached_subjects(cache_key, logger)
            if cached:
                logger.debug("returning cached subjects", curriculum_id=str(curriculum.id))
                return {"items": cached}
        else:
            logger.info(
                "subjects are stale, bypassing cache",
                curriculum_id=str(curriculum.id),
                updated_at=curriculum.timetable_updated_at.isoformat() if curriculum.timetable_updated_at else None,
            )

    subjects = await fetch_and_save_subjects(
        session,
        course,
        curriculum,
        logger,
        active_only=not include_inactive,
    )

    if not include_inactive:
        await cache.set_cached_subjects(cache_key, subjects, logger)

    return {"items": subjects}
