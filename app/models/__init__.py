from app.models.generated import (
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
from app.utils.database import Base

__all__ = [
    "Base",
    "Courses",
    "Curricula",
    "Subjects",
    "TimetableEvents",
    "Classrooms",
    "CalendarLinks",
    "CalendarCourses",
    "CalendarSubjects",
    "CalendarSubscriptions",
    "Users",
    "OauthProviders",
    "RefreshTokens",
    "SchemaMigrations",
]
