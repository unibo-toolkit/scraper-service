from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ClassroomBase(BaseModel):
    """Base classroom schema"""

    name: str
    address: Optional[str] = None
    building: Optional[str] = None


class Classroom(ClassroomBase):
    """Full classroom schema"""

    id: int
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TimetableEventBase(BaseModel):
    """Base timetable event schema"""

    title: str = Field(..., description="Event title")
    start: datetime = Field(..., description="Event start time")
    end: datetime = Field(..., description="Event end time")
    classroom_name: Optional[str] = Field(None, description="Classroom name")
    teachers: Optional[str] = Field(None, description="Teachers (comma-separated)")
    event_type: Optional[str] = Field(None, description="Event type (lecture, lab, etc)")


class TimetableEvent(TimetableEventBase):
    """Full timetable event schema"""

    id: int
    subject_id: int
    classroom_id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TimetableEventWithClassroom(TimetableEvent):
    """Timetable event with classroom details"""

    classroom: Optional[Classroom] = None


class TimetableRequest(BaseModel):
    """Request for fetching timetable"""

    subject_ids: List[int] = Field(..., description="List of subject IDs", min_length=1)
    start_date: Optional[datetime] = Field(None, description="Filter events from this date")
    end_date: Optional[datetime] = Field(None, description="Filter events until this date")


class TimetableResponse(BaseModel):
    """Response with timetable events"""

    events: List[TimetableEventWithClassroom]
    total: int
    cached: bool = Field(False, description="Whether data was served from cache")


class TimetableRefreshRequest(BaseModel):
    """Request for refreshing timetable."""

    subject_ids: List[int] = Field(..., description="List of subject IDs to refresh")
    force: bool = Field(False, description="Force refresh even if hash hasn't changed")


class TimetableRefreshResponse(BaseModel):
    """Response for timetable refresh."""

    refreshed: int = Field(..., description="Number of subjects refreshed")
    skipped: int = Field(..., description="Number of subjects skipped (no changes)")
    errors: int = Field(..., description="Number of subjects with errors")
    details: List[dict] = Field(default_factory=list, description="Details per subject")
