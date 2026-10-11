from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.exceptions import NotFoundError
from app.api.v1.schemas import CourseResponse, CoursesResponse
from app.core.catalog import CourseCatalog
from app.utils.custom_logger import CustomLogger
from app.utils.database import get_db

router = APIRouter()


@router.get("/courses", response_model=CoursesResponse)
async def get_courses(
    q: Optional[str] = Query(None, description="Search by title"),
    course_type: Optional[str] = Query(
        None, alias="type", pattern="^(Bachelor|Master|SingleCycleMaster)$"
    ),
    lang: str = Query("it", pattern="^(it|en)$"),
    limit: int = Query(50, ge=1, le=300),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    logger = CustomLogger("api:get_courses", lang=lang, type=course_type, q=q)
    logger.info("handling get courses request")

    page = await CourseCatalog(session, logger).search(
        query=q, course_type=course_type, limit=limit, offset=offset
    )

    return CoursesResponse(
        items=[CourseResponse.of(course, lang) for course in page.items],
        total=page.total,
        limit=limit,
        offset=offset,
    )


@router.get("/courses/{course_id}", response_model=CourseResponse)
async def get_course_by_id(
    course_id: UUID,
    lang: str = Query("it", pattern="^(it|en)$"),
    session: AsyncSession = Depends(get_db),
):
    logger = CustomLogger("api:get_course_by_id", course_id=str(course_id), lang=lang)
    logger.info("handling get course by id request")

    course = await CourseCatalog(session, logger).get(course_id)
    if not course:
        raise NotFoundError(f"Course with ID {course_id} not found")

    return CourseResponse.of(course, lang)
