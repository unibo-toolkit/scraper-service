from fastapi import APIRouter, Query, Depends
from typing import List
from uuid import UUID
from datetime import datetime, timedelta, UTC
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.custom_logger import CustomLogger
from app.utils.database import get_db
from app.core.database import DatabaseOperations
from app.core.subjects import fetch_and_save_subjects
from app.core import cache

router = APIRouter()


def _get_week_monday(target_date: datetime) -> datetime:
    current_weekday = target_date.weekday()
    monday = (target_date - timedelta(days=current_weekday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return monday


def _find_closest_event(events: List, reference_date: datetime):
    if not events:
        return None

    return min(events, key=lambda e: abs((e.start_datetime - reference_date).total_seconds()))


def _format_event(event):
    return {
        "id": str(event.id),
        "subject_id": str(event.subject_id),
        "title": event.title,
        "start_datetime": event.start_datetime.isoformat(),
        "end_datetime": event.end_datetime.isoformat(),
        "is_remote": event.is_remote,
        "professor": event.professor,
        "module_code": event.module_code,
        "credits": event.credits if event.credits else None,
        "teams_link": event.teams_link,
        "notes": event.notes,
        "group_id": event.group_id,
        "classroom": {
            "id": str(event.classroom.id),
            "name": event.classroom.name,
            "address": event.classroom.address,
            "latitude": float(event.classroom.latitude) if event.classroom.latitude else None,
            "longitude": float(event.classroom.longitude) if event.classroom.longitude else None,
        } if event.classroom else None
    }


@router.get("/timetable")
async def get_timetable(
    subject_ids: List[UUID] = Query(..., description="List of subject UUIDs"),
    session: AsyncSession = Depends(get_db)
):
    logger = CustomLogger("api:get_timetable")
    logger.info("handling get timetable request", subject_count=len(subject_ids))

    db_ops = DatabaseOperations(session, logger)

    events = await db_ops.get_timetable_events_by_subject_ids(subject_ids)

    return {
        "items": [_format_event(event) for event in events],
        "total": len(events)
    }


@router.post("/timetable/refresh")
async def refresh_timetable(
    subject_ids: List[UUID] = Query(..., description="List of subject UUIDs"),
    session: AsyncSession = Depends(get_db)
):
    logger = CustomLogger("api:refresh_timetable")
    logger.info("handling refresh timetable request", subject_count=len(subject_ids))

    db_ops = DatabaseOperations(session, logger)

    curriculum_ids = set()
    for subject_id in subject_ids:
        subject = await db_ops.get_subject_by_id(subject_id)
        if subject:
            curriculum_ids.add(subject.curriculum_id)

    if not curriculum_ids:
        logger.warning("no valid subjects found")
        return {
            "status": "completed",
            "updated": 0
        }

    updated_count = 0

    for curriculum_id in curriculum_ids:
        curriculum = await db_ops.get_curriculum_by_id(curriculum_id)
        if not curriculum:
            logger.warning("curriculum not found", curriculum_id=str(curriculum_id))
            continue

        course = await db_ops.get_course_by_curriculum(curriculum_id)
        if not course:
            logger.warning("course not found for curriculum", curriculum_id=str(curriculum_id))
            continue

        try:
            await fetch_and_save_subjects(session, course, curriculum, logger)

            cache_key = f"subjects:{curriculum.id}"
            await cache.delete_cached_subjects(cache_key, logger)

            updated_count += 1
        except Exception as e:
            logger.error("failed to refresh curriculum", curriculum_id=str(curriculum_id), error=str(e))
            continue

    await session.commit()

    logger.info("timetable refresh completed", updated=updated_count)

    return {
        "status": "completed",
        "updated": updated_count
    }


@router.get("/preview")
async def preview_timetable(
    subject_ids: List[UUID] = Query(..., description="List of subject UUIDs"),
    page: int = Query(0, description="Page offset in weeks from the target event week"),
    session: AsyncSession = Depends(get_db)
):
    logger = CustomLogger("api:preview_timetable")
    logger.info("handling preview timetable request", subject_count=len(subject_ids), page=page)

    db_ops = DatabaseOperations(session, logger)

    all_events = await db_ops.get_timetable_events_by_subject_ids(subject_ids)

    if not all_events:
        return {
            "items": [],
            "from_date": None,
            "to_date": None,
            "total": 0,
            "target": None
        }

    now = datetime.now(UTC)
    target_event = _find_closest_event(all_events, now)

    target_monday = _get_week_monday(target_event.start_datetime) + timedelta(weeks=page)
    from_date = target_monday - timedelta(weeks=1)
    to_date = target_monday + timedelta(weeks=2)

    preview_events = [e for e in all_events if from_date <= e.start_datetime < to_date]

    actual_from_date = min(e.start_datetime for e in preview_events) if preview_events else from_date
    actual_to_date = max(e.start_datetime for e in preview_events) if preview_events else to_date

    return {
        "items": [_format_event(event) for event in preview_events],
        "from_date": actual_from_date.isoformat(),
        "to_date": actual_to_date.isoformat(),
        "total": len(preview_events),
        "target": _format_event(target_event) if target_event else None
    }
