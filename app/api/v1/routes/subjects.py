from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.api.exceptions import NotFoundError
from app.api.v1.schemas import SubjectsResponse
from app.core.cache import SubjectsCache
from app.core.database import CurriculaOperations
from app.core.timetable import TimetableSync, is_fresh
from app.utils.custom_logger import CustomLogger
from app.utils.database import get_db

router = APIRouter()


@router.get("/courses/{course_id}/curricula/{curricula_id}/subjects", response_model=SubjectsResponse)
async def get_course_subjects(
    course_id: UUID,
    curricula_id: UUID,
    include_inactive: bool = Query(False, description="Include inactive subjects"),
    format_titles: bool = Query(False, description="Apply title formatting (preview)"),
    session: AsyncSession = Depends(get_db),
):
    logger = CustomLogger("api:get_course_subjects", curriculum_id=str(curricula_id))
    logger.info("handling get course subjects request")

    pair = await CurriculaOperations(session, logger).get(curricula_id)
    if not pair:
        raise NotFoundError(f"Curriculum {curricula_id} not found")
    if pair.course.id != course_id:
        raise NotFoundError(
            f"Curriculum {curricula_id} does not belong to course {course_id}"
        )

    if not include_inactive:
        cached = await __fresh_cache(pair.curriculum, logger)
        if cached is not None:
            return SubjectsResponse.of(cached, format_titles)

    subjects = await TimetableSync(session, logger).sync(
        pair, active_only=not include_inactive
    )
    return SubjectsResponse.of(subjects, format_titles)


async def __fresh_cache(curriculum, logger: CustomLogger):
    """
    Cached subjects are served only while the timetable itself is recent
    enough, otherwise the sync has to run first.
    """
    threshold = datetime.now(UTC) - timedelta(seconds=config.scraper.subjects_refresh_ttl)

    if not is_fresh(curriculum.timetable_updated_at, threshold):
        logger.info(
            "subjects are stale, bypassing cache",
            updated_at=curriculum.timetable_updated_at.isoformat()
            if curriculum.timetable_updated_at
            else None,
        )
        return None

    return await SubjectsCache(logger).get(curriculum.id)
