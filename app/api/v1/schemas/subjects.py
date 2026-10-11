from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.timetable import Subject
from app.utils.title_formatter import format_event_title


class SubjectResponse(BaseModel):
    id: UUID
    title: str
    module_code: Optional[str]
    credits: Optional[int]
    professor: Optional[str]
    group_id: Optional[str]

    @classmethod
    def of(cls, subject: Subject, format_titles: bool = False) -> "SubjectResponse":
        return cls(
            id=subject.id,
            title=format_event_title(subject.title) if format_titles else subject.title,
            module_code=subject.module_code,
            credits=subject.credits,
            professor=subject.professor,
            group_id=subject.group_id,
        )


class SubjectsResponse(BaseModel):
    items: List[SubjectResponse]

    @classmethod
    def of(cls, subjects: List[Subject], format_titles: bool = False) -> "SubjectsResponse":
        return cls(items=[SubjectResponse.of(s, format_titles) for s in subjects])
