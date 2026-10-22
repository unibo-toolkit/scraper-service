from app.models.courses import Course, CourseCurriculum, Curriculum
from app.models.generated import (
    Base,
    CalendarCourses,
    CalendarLinks,
    CalendarSubjects,
    CalendarSubscriptions,
    Classrooms,
    Courses,
    Curricula,
    OauthProviders,
    RefreshTokens,
    SchemaMigrations,
    Subjects,
    TimetableEvents,
    Users,
)
from app.models.timetable import Classroom, ClassroomKey, Event, Subject, SubjectKey, Timetable

__all__ = [
    # ORM
    "Base",
    "CalendarCourses",
    "CalendarLinks",
    "CalendarSubjects",
    "CalendarSubscriptions",
    "Classrooms",
    "Courses",
    "Curricula",
    "OauthProviders",
    "RefreshTokens",
    "SchemaMigrations",
    "Subjects",
    "TimetableEvents",
    "Users",
    # domain
    "Classroom",
    "ClassroomKey",
    "Course",
    "CourseCurriculum",
    "Curriculum",
    "Event",
    "Subject",
    "SubjectKey",
    "Timetable",
]
