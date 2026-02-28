from fastapi import APIRouter, Query, Depends
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.custom_logger import CustomLogger
from app.utils.database import get_db
from app.core import cache
from app.core.subjects import fetch_and_save_subjects
from app.core.database import DatabaseOperations
from app.api.exceptions import NotFoundError

router = APIRouter()


@router.get("/courses/{course_id}/subjects")
async def get_course_subjects(
    course_id: UUID,
    curriculum_id: UUID = Query(..., description="Curriculum UUID"),
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
    cached = await cache.get_cached_subjects(cache_key, logger)
    if cached:
        return {"items": cached}

    subjects = await fetch_and_save_subjects(
        session,
        course,
        curriculum,
        logger
    )

    await cache.set_cached_subjects(cache_key, subjects, logger)

    return {"items": subjects}
