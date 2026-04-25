from fastapi import APIRouter, Query, Depends
from typing import List
from uuid import UUID
from datetime import datetime, timedelta, UTC
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.custom_logger import CustomLogger
from app.utils.database import get_db
from app.utils.title_formatter import format_event_title
from app.core.database import DatabaseOperations
from app.core.subjects import fetch_and_save_subjects
from app.core import cache
from app import config

router = APIRouter()


def _get_week_monday(target_date: datetime) -> datetime:
    current_weekday = target_date.weekday()
    monday = (target_date - timedelta(days=current_weekday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return monday


def _find_anchor_event(events: List, reference_date: datetime):
    if not events:
        return None

    future = [e for e in events if e.start_datetime >= reference_date]
    if future:
        return min(future, key=lambda e: (e.start_datetime - reference_date).total_seconds())

    return max(events, key=lambda e: e.start_datetime)


def _find_closest_to_date(events: List, reference_date: datetime):
    if not events:
        return None

    return min(events, key=lambda e: abs((e.start_datetime - reference_date).total_seconds()))


def _format_event(event, format_titles: bool = False):
    return {
        "id": str(event.id),
        "subject_id": str(event.subject_id),
        "title": format_event_title(event.title) if format_titles else event.title,
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


async def _refresh_stale_curricula(
    subject_ids: List[UUID],
    session: AsyncSession,
    db_ops: DatabaseOperations,
    logger: CustomLogger,
) -> bool:
    threshold = datetime.now(UTC) - timedelta(seconds=config.scraper.timetable_events_ttl)
    curricula = await db_ops.get_curricula_by_subject_ids(subject_ids)

    refreshed = False
    for curriculum in curricula:
        is_fresh = curriculum.timetable_updated_at and curriculum.timetable_updated_at > threshold

        if is_fresh:
            if await db_ops.has_curriculum_events(curriculum.id):
                logger.debug(
                    "timetable is fresh, skipping refresh",
                    curriculum_id=str(curriculum.id),
                    updated_at=curriculum.timetable_updated_at.isoformat(),
                )
                continue
            logger.info("timetable is fresh but no events in db, forcing refresh", curriculum_id=str(curriculum.id))
        else:
            logger.info(
                "timetable is stale, refreshing",
                curriculum_id=str(curriculum.id),
                updated_at=curriculum.timetable_updated_at.isoformat() if curriculum.timetable_updated_at else None,
            )

        await fetch_and_save_subjects(session, curriculum.course, curriculum, logger, force_update=bool(is_fresh))
        await cache.delete_cached_subjects(f"subjects:{curriculum.id}", logger)
        refreshed = True

    return refreshed


@router.get("/timetable")
@router.deprecated("Use preview only", category=DeprecationWarning)
async def get_timetable(
    subject_ids: List[UUID] = Query(..., description="List of subject UUIDs"),
    session: AsyncSession = Depends(get_db)
):
    logger = CustomLogger("api:get_timetable")
    logger.info("handling get timetable request", subject_count=len(subject_ids))

    db_ops = DatabaseOperations(session, logger)

    await _refresh_stale_curricula(subject_ids, session, db_ops, logger)

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
    format_titles: bool = Query(False, description="Apply title formatting (preview)"),
    session: AsyncSession = Depends(get_db)
):
    logger = CustomLogger("api:preview_timetable")
    logger.info("handling preview timetable request", subject_count=len(subject_ids), page=page)

    db_ops = DatabaseOperations(session, logger)

    await _refresh_stale_curricula(subject_ids, session, db_ops, logger)

    all_events = await db_ops.get_timetable_events_by_subject_ids(subject_ids)

    if not all_events:
        return {
            "items": [],
            "from_date": None,
            "to_date": None,
            "total": 0,
            "courses_events_count": 0,
            "target": None
        }

    now = datetime.now(UTC)
    anchor_event = _find_anchor_event(all_events, now)

    page_monday = _get_week_monday(anchor_event.start_datetime) + timedelta(weeks=page)
    from_date = page_monday - timedelta(weeks=1)
    to_date = page_monday + timedelta(weeks=2)

    preview_events = [e for e in all_events if from_date <= e.start_datetime < to_date]
    target_event = _find_closest_to_date(preview_events, page_monday)

    return {
        "items": [_format_event(event, format_titles) for event in preview_events],
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "total": len(preview_events),
        "courses_events_count": len(all_events),
        "target": _format_event(target_event, format_titles) if target_event else None
    }
