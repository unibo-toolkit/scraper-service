from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

from unibo_toolkit import Area, BaseCourse
from unibo_toolkit.models import Classroom as UniBoClassroom
from unibo_toolkit.models import Curriculum as UniBoCurriculum
from unibo_toolkit.models import CurriculumTimetable, TimetableEvent

from app.models.courses import Course, Curriculum
from app.models.timetable import ROME_TZ, Classroom, Event, Timetable

COURSE_TYPES = {
    "bachelor": "Bachelor",
    "master": "Master",
    "combined_bachelor_master": "SingleCycleMaster",
    "single_cycle": "SingleCycleMaster",
    "single_cycle_master": "SingleCycleMaster",
}
DEFAULT_COURSE_TYPE = "Master"


def to_course(
    course: BaseCourse,
    title_en: Optional[str] = None,
    curricula: Sequence[UniBoCurriculum] = (),
) -> Course:
    return Course(
        unibo_id=course.course_id,
        title_it=course.title,
        title_en=title_en,
        course_type=COURSE_TYPES.get(course.get_course_type().value, DEFAULT_COURSE_TYPE),
        campus=course.campus.value if course.campus else None,
        languages=tuple(lang.value for lang in (course.languages or [])),
        duration_years=course.duration_years,
        url=course.course_site_url,
        area=_area(course.area),
        curricula=tuple(Curriculum(code=c.code, label=c.label) for c in curricula),
    )


def to_timetable(timetable: CurriculumTimetable) -> Timetable:
    return Timetable(
        content_hash=timetable.content_hash,
        events=tuple(to_event(event) for event in timetable.events),
    )


def to_event(event: TimetableEvent) -> Event:
    return Event(
        title=event.title,
        start=_rome_tz(event.start),
        end=_rome_tz(event.end),
        professor=event.professor,
        module_code=event.module_code,
        credits=Decimal(event.credits) if event.credits is not None else None,
        group_id=_group_id(event),
        classroom=to_classroom(event.primary_classroom),
        location=event.primary_classroom.title if event.primary_classroom else None,
        is_remote=event.is_remote,
        teams_link=event.teams_link,
        notes=event.notes,
    )


def to_classroom(classroom: Optional[UniBoClassroom]) -> Optional[Classroom]:
    """
    Nameless classrooms are dropped: the name is the only thing identifying
    them and the column is NOT NULL.
    """
    if not classroom or not classroom.title:
        return None

    return Classroom(
        name=classroom.title,
        address=classroom.address,
        latitude=_coordinate(classroom.latitude),
        longitude=_coordinate(classroom.longitude),
    )


def _group_id(event: TimetableEvent) -> Optional[str]:
    """
    unibo_toolkit also derives the group from the event title, which yields
    false positives like "(I)" or "(EN)". Only cod_sdoppiamento is trusted.
    """
    if not event.cod_sdoppiamento:
        return None
    return TimetableEvent.extract_group_id(event.cod_sdoppiamento)


def _rome_tz(value: datetime) -> datetime:
    return value.replace(tzinfo=ROME_TZ) if value.tzinfo is None else value


def _coordinate(value: Optional[float]) -> Optional[Decimal]:
    return Decimal(str(value)) if value is not None else None


def _area(area: Optional[Area]) -> Optional[str]:
    if not area:
        return None

    value = getattr(area, "value", area)
    if isinstance(value, tuple):
        return value[1] if len(value) > 1 else value[0]
    return str(value)
