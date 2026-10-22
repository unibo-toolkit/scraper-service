from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.courses import Course, Curriculum


class CurriculumResponse(BaseModel):
    id: UUID
    code: str
    label: str
    academic_year: Optional[int]

    @classmethod
    def of(cls, curriculum: Curriculum) -> "CurriculumResponse":
        return cls(
            id=curriculum.id,
            code=curriculum.code,
            label=curriculum.label,
            academic_year=curriculum.academic_year,
        )


class CourseResponse(BaseModel):
    id: UUID
    unibo_id: int
    title: str
    course_type: str
    campus: Optional[str]
    languages: List[str]
    duration_years: Optional[int]
    url: Optional[str]
    area: Optional[str]
    curricula: List[CurriculumResponse]

    @classmethod
    def of(cls, course: Course, lang: str) -> "CourseResponse":
        return cls(
            id=course.id,
            unibo_id=course.unibo_id,
            title=course.title(lang),
            course_type=course.course_type,
            campus=course.campus,
            languages=list(course.languages),
            duration_years=course.duration_years,
            url=course.url,
            area=course.area,
            curricula=[
                CurriculumResponse.of(curr)
                for curr in sorted(course.curricula, key=lambda curr: curr.code)
            ],
        )


class CoursesResponse(BaseModel):
    items: List[CourseResponse]
    total: int
    limit: int
    offset: int
