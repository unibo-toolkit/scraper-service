from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CurriculumBase(BaseModel):
    """Base curriculum schema"""

    name: str
    year: int


class Curriculum(CurriculumBase):
    """Full curriculum schema"""

    id: int
    course_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SubjectBase(BaseModel):
    """Base subject schema"""

    name: str
    timetable_url: Optional[str] = None


class Subject(SubjectBase):
    """Full subject schema"""

    id: int
    curriculum_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CourseBase(BaseModel):
    """Base course schema"""

    title_it: str = Field(..., description="Course title in Italian")
    title_en: Optional[str] = Field(None, description="Course title in English")
    course_url: str = Field(..., description="URL to course page")


class Course(CourseBase):
    """Full course schema with metadata"""

    id: int
    timetable_hash: Optional[str] = Field(None, description="Content hash of timetable")
    timetable_updated_at: Optional[datetime] = Field(None, description="Last timetable update")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CourseWithCurricula(Course):
    """Course with nested curricula"""

    curricula: List[Curriculum] = []


class CourseWithSubjects(Course):
    """Course with nested subjects"""

    curricula: List[Curriculum] = []
    subjects: List[Subject] = []


class CoursesList(BaseModel):
    """Paginated list of courses"""

    courses: List[Course]
    total: int
    limit: int
    offset: int


class CourseUpdate(BaseModel):
    """Schema for updating course"""

    title_it: Optional[str] = None
    title_en: Optional[str] = None
    timetable_hash: Optional[str] = None
    timetable_updated_at: Optional[datetime] = None
