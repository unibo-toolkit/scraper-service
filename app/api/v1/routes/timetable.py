from datetime import UTC, datetime, timedelta
from typing import List, Optional, Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import EventResponse, PreviewResponse, RefreshResponse, TimetableResponse
from app.core.database import CurriculaOperations, EventsOperations
from app.core.timetable import TimetableSync
from app.models.timetable import Event
from app.utils.custom_logger import CustomLogger
from app.utils.database import get_db

router = APIRouter()

PREVIEW_WEEKS_BEFORE = 1
PREVIEW_WEEKS_AFTER = 2


@router.get("/timetable", deprecated=True, response_model=TimetableResponse)
async def get_timetable(
    subject_ids: List[UUID] = Query(..., description="List of subject UUIDs"),
    session: AsyncSession = Depends(get_db),
):
    logger = CustomLogger("api:get_timetable", subject_count=len(subject_ids))
    logger.info("handling get timetable request")

    await TimetableSync(session, logger).refresh_stale(subject_ids)
    events = await EventsOperations(session, logger).list_by_subjects(subject_ids)

    return TimetableResponse.of(events)


@router.post("/timetable/refresh", response_model=RefreshResponse)
async def refresh_timetable(
    subject_ids: List[UUID] = Query(..., description="List of subject UUIDs"),
    session: AsyncSession = Depends(get_db),
):
    logger = CustomLogger("api:refresh_timetable", subject_count=len(subject_ids))
    logger.info("handling refresh timetable request")

    pairs = await CurriculaOperations(session, logger).list_by_subjects(subject_ids)
    if not pairs:
        logger.warning("no valid subjects found")
        return RefreshResponse(status="completed", updated=0)

    sync = TimetableSync(session, logger)
    updated = 0
    for pair in pairs:
        try:
            await sync.sync(pair)
            updated += 1
        except Exception as e:
            await session.rollback()
            logger.error(
                "failed to refresh curriculum",
                curriculum_id=str(pair.curriculum.id),
                error=str(e),
            )

    logger.info("timetable refresh completed", updated=updated)
    return RefreshResponse(status="completed", updated=updated)


@router.get("/preview", response_model=PreviewResponse)
async def preview_timetable(
    subject_ids: List[UUID] = Query(..., description="List of subject UUIDs"),
    page: int = Query(0, description="Page offset in weeks from the target event week"),
    format_titles: bool = Query(False, description="Apply title formatting (preview)"),
    session: AsyncSession = Depends(get_db),
):
    logger = CustomLogger("api:preview_timetable", subject_count=len(subject_ids), page=page)
    logger.info("handling preview timetable request")

    await TimetableSync(session, logger).refresh_stale(subject_ids)
    events = await EventsOperations(session, logger).list_by_subjects(subject_ids)

    if not events:
        return PreviewResponse(
            items=[], from_date=None, to_date=None, total=0, courses_events_count=0, target=None
        )

    anchor = _anchor(events, datetime.now(UTC))
    monday = _week_monday(anchor.start) + timedelta(weeks=page)
    from_date = monday - timedelta(weeks=PREVIEW_WEEKS_BEFORE)
    to_date = monday + timedelta(weeks=PREVIEW_WEEKS_AFTER)

    window = [event for event in events if from_date <= event.start < to_date]
    target = _closest_to(window, monday)

    return PreviewResponse(
        items=[EventResponse.of(event, format_titles) for event in window],
        from_date=from_date,
        to_date=to_date,
        total=len(window),
        courses_events_count=len(events),
        target=EventResponse.of(target, format_titles) if target else None,
    )


def _week_monday(value: datetime) -> datetime:
    monday = value - timedelta(days=value.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def _anchor(events: Sequence[Event], now: datetime) -> Event:
    """
    First event from now on, or the last one if the timetable is over.
    """
    upcoming = [event for event in events if event.start >= now]
    if upcoming:
        return min(upcoming, key=lambda event: event.start)

    return max(events, key=lambda event: event.start)


def _closest_to(events: Sequence[Event], moment: datetime) -> Optional[Event]:
    if not events:
        return None

    return min(events, key=lambda event: abs((event.start - moment).total_seconds()))
