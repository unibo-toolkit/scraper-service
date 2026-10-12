from datetime import datetime
from typing import Annotated, List, Optional
from uuid import UUID

from pydantic import BaseModel, PlainSerializer

from app.models.timetable import Classroom, Event
from app.utils.title_formatter import format_event_title

# Pydantic renders a UTC datetime as "...Z", while the API has always sent the
# "+00:00" form that datetime.isoformat() produces.
IsoDatetime = Annotated[
    datetime,
    PlainSerializer(lambda value: value.isoformat(), return_type=str, when_used="json"),
]


class ClassroomResponse(BaseModel):
    id: UUID
    name: str
    address: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]

    @classmethod
    def of(cls, classroom: Classroom) -> "ClassroomResponse":
        return cls(
            id=classroom.id,
            name=classroom.name,
            address=classroom.address,
            latitude=float(classroom.latitude) if classroom.latitude is not None else None,
            longitude=float(classroom.longitude) if classroom.longitude is not None else None,
        )


class EventResponse(BaseModel):
    id: UUID
    subject_id: UUID
    title: str
    start_datetime: IsoDatetime
    end_datetime: IsoDatetime
    is_remote: bool
    professor: Optional[str]
    module_code: Optional[str]
    credits: Optional[float]
    teams_link: Optional[str]
    notes: Optional[str]
    group_id: Optional[str]
    family_hash: str
    weekday: int
    slot_start: str
    classroom: Optional[ClassroomResponse]

    @classmethod
    def of(cls, event: Event, format_titles: bool = False) -> "EventResponse":
        return cls(
            id=event.id,
            subject_id=event.subject_id,
            title=format_event_title(event.title) if format_titles else event.title,
            start_datetime=event.start,
            end_datetime=event.end,
            is_remote=event.is_remote,
            professor=event.professor,
            module_code=event.module_code,
            credits=float(event.credits) if event.credits else None,
            teams_link=event.teams_link,
            notes=event.notes,
            group_id=event.group_id,
            family_hash=event.family_hash,
            weekday=event.slot.weekday,
            slot_start=event.slot.start_time,
            classroom=ClassroomResponse.of(event.classroom) if event.classroom else None,
        )


class TimetableResponse(BaseModel):
    items: List[EventResponse]
    total: int

    @classmethod
    def of(cls, events: List[Event]) -> "TimetableResponse":
        return cls(items=[EventResponse.of(event) for event in events], total=len(events))


class PreviewResponse(BaseModel):
    items: List[EventResponse]
    from_date: Optional[IsoDatetime]
    to_date: Optional[IsoDatetime]
    total: int
    courses_events_count: int
    target: Optional[EventResponse]


class RefreshResponse(BaseModel):
    status: str
    updated: int
