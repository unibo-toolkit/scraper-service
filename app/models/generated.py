from typing import Optional
import datetime
import decimal
import uuid

from sqlalchemy import ARRAY, BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKeyConstraint, Index, Integer, Numeric, PrimaryKeyConstraint, SmallInteger, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Classrooms(Base):
    __tablename__ = 'classrooms'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='classrooms_pkey'),
        UniqueConstraint('name', 'address', name='classrooms_name_address_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)
    latitude: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(9, 6))

    timetable_events: Mapped[list['TimetableEvents']] = relationship('TimetableEvents', back_populates='classroom')


class Courses(Base):
    __tablename__ = 'courses'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='courses_pkey'),
        UniqueConstraint('unibo_id', name='courses_unibo_id_key'),
        Index('idx_courses_timetable_updated', 'timetable_updated_at'),
        Index('idx_courses_title_en_trgm', 'title_en'),
        Index('idx_courses_title_it_trgm', 'title_it'),
        Index('idx_courses_unibo_id', 'unibo_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    unibo_id: Mapped[int] = mapped_column(Integer, nullable=False)
    course_type: Mapped[str] = mapped_column(Enum('Bachelor', 'Master', 'SingleCycleMaster', name='course_type'), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    title_it: Mapped[str] = mapped_column(String(500), nullable=False)
    campus: Mapped[Optional[str]] = mapped_column(String(255))
    languages: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(length=255)))
    duration_years: Mapped[Optional[int]] = mapped_column(SmallInteger)
    url: Mapped[Optional[str]] = mapped_column(Text)
    area: Mapped[Optional[str]] = mapped_column(String(255))
    timetable_hash: Mapped[Optional[str]] = mapped_column(String(64))
    timetable_updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    title_en: Mapped[Optional[str]] = mapped_column(String(500))

    curricula: Mapped[list['Curricula']] = relationship('Curricula', back_populates='course')


class SchemaMigrations(Base):
    __tablename__ = 'schema_migrations'
    __table_args__ = (
        PrimaryKeyConstraint('version', name='schema_migrations_pkey'),
    )

    version: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dirty: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Users(Base):
    __tablename__ = 'users'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='users_pkey'),
        UniqueConstraint('email', name='users_email_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    last_login: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    calendar_links: Mapped[list['CalendarLinks']] = relationship('CalendarLinks', back_populates='owner')
    oauth_providers: Mapped[list['OauthProviders']] = relationship('OauthProviders', back_populates='user')
    refresh_tokens: Mapped[list['RefreshTokens']] = relationship('RefreshTokens', back_populates='user')


class CalendarLinks(Base):
    __tablename__ = 'calendar_links'
    __table_args__ = (
        ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='SET NULL', name='calendar_links_owner_id_fkey'),
        PrimaryKeyConstraint('id', name='calendar_links_pkey'),
        UniqueConstraint('slug', name='calendar_links_slug_key'),
        Index('idx_calendar_links_owner_id', 'owner_id'),
        Index('idx_calendar_links_slug', 'slug'),
        Index('idx_calendar_links_ttl', 'ttl_expires_at')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    slug: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("'My Calendar'::character varying"))
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    ttl_expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    description: Mapped[Optional[str]] = mapped_column(Text)
    last_accessed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    owner: Mapped[Optional['Users']] = relationship('Users', back_populates='calendar_links')
    calendar_courses: Mapped[list['CalendarCourses']] = relationship('CalendarCourses', back_populates='calendar')
    calendar_subscriptions: Mapped[list['CalendarSubscriptions']] = relationship('CalendarSubscriptions', back_populates='calendar')
    calendar_events: Mapped[list['CalendarEvents']] = relationship('CalendarEvents', back_populates='calendar')


class Curricula(Base):
    __tablename__ = 'curricula'
    __table_args__ = (
        CheckConstraint('academic_year >= 1', name='curricula_academic_year_check'),
        ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE', name='curricula_course_id_fkey'),
        PrimaryKeyConstraint('id', name='curricula_pkey'),
        UniqueConstraint('course_id', 'code', 'academic_year', name='curricula_course_id_code_academic_year_key'),
        Index('idx_curricula_course_code_year', 'course_id', 'code', 'academic_year'),
        Index('idx_curricula_course_id', 'course_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    course_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    academic_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))

    course: Mapped['Courses'] = relationship('Courses', back_populates='curricula')
    calendar_courses: Mapped[list['CalendarCourses']] = relationship('CalendarCourses', back_populates='curriculum')
    subjects: Mapped[list['Subjects']] = relationship('Subjects', back_populates='curriculum')


class OauthProviders(Base):
    __tablename__ = 'oauth_providers'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='oauth_providers_user_id_fkey'),
        PrimaryKeyConstraint('id', name='oauth_providers_pkey'),
        UniqueConstraint('provider', 'provider_id', name='oauth_providers_provider_provider_id_key'),
        Index('idx_oauth_providers_user_id', 'user_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))

    user: Mapped['Users'] = relationship('Users', back_populates='oauth_providers')


class RefreshTokens(Base):
    __tablename__ = 'refresh_tokens'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='refresh_tokens_user_id_fkey'),
        PrimaryKeyConstraint('id', name='refresh_tokens_pkey'),
        UniqueConstraint('token_hash', name='refresh_tokens_token_hash_key'),
        Index('idx_refresh_tokens_expires_at', 'expires_at'),
        Index('idx_refresh_tokens_token_hash', 'token_hash'),
        Index('idx_refresh_tokens_user_id', 'user_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    revoked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    user: Mapped['Users'] = relationship('Users', back_populates='refresh_tokens')


class CalendarCourses(Base):
    __tablename__ = 'calendar_courses'
    __table_args__ = (
        ForeignKeyConstraint(['calendar_id'], ['calendar_links.id'], ondelete='CASCADE', name='calendar_courses_calendar_id_fkey'),
        ForeignKeyConstraint(['curriculum_id'], ['curricula.id'], ondelete='RESTRICT', name='calendar_courses_curriculum_id_fkey'),
        PrimaryKeyConstraint('id', name='calendar_courses_pkey'),
        UniqueConstraint('calendar_id', 'curriculum_id', name='calendar_courses_calendar_id_curriculum_id_key'),
        Index('idx_calendar_courses_calendar_id', 'calendar_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    calendar_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    curriculum_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text('0'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))

    calendar: Mapped['CalendarLinks'] = relationship('CalendarLinks', back_populates='calendar_courses')
    curriculum: Mapped['Curricula'] = relationship('Curricula', back_populates='calendar_courses')
    calendar_subjects: Mapped[list['CalendarSubjects']] = relationship('CalendarSubjects', back_populates='calendar_course')


class CalendarSubscriptions(Base):
    __tablename__ = 'calendar_subscriptions'
    __table_args__ = (
        ForeignKeyConstraint(['calendar_id'], ['calendar_links.id'], ondelete='CASCADE', name='calendar_subscriptions_calendar_id_fkey'),
        PrimaryKeyConstraint('id', name='calendar_subscriptions_pkey'),
        Index('idx_calendar_subscriptions_calendar_id', 'calendar_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    calendar_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    last_request_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64))

    calendar: Mapped['CalendarLinks'] = relationship('CalendarLinks', back_populates='calendar_subscriptions')


class Subjects(Base):
    __tablename__ = 'subjects'
    __table_args__ = (
        ForeignKeyConstraint(['curriculum_id'], ['curricula.id'], ondelete='CASCADE', name='subjects_curriculum_id_fkey'),
        PrimaryKeyConstraint('id', name='subjects_pkey'),
        Index('idx_subjects_curriculum_id', 'curriculum_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    curriculum_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    module_code: Mapped[Optional[str]] = mapped_column(String(50))
    group_id: Mapped[Optional[str]] = mapped_column(String(50))
    credits: Mapped[Optional[int]] = mapped_column(SmallInteger)
    professor: Mapped[Optional[str]] = mapped_column(String(255))

    curriculum: Mapped['Curricula'] = relationship('Curricula', back_populates='subjects')
    calendar_subjects: Mapped[list['CalendarSubjects']] = relationship('CalendarSubjects', back_populates='subject')
    timetable_events: Mapped[list['TimetableEvents']] = relationship('TimetableEvents', back_populates='subject')


class CalendarSubjects(Base):
    __tablename__ = 'calendar_subjects'
    __table_args__ = (
        ForeignKeyConstraint(['calendar_course_id'], ['calendar_courses.id'], ondelete='CASCADE', name='calendar_subjects_calendar_course_id_fkey'),
        ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='RESTRICT', name='calendar_subjects_subject_id_fkey'),
        PrimaryKeyConstraint('id', name='calendar_subjects_pkey'),
        UniqueConstraint('calendar_course_id', 'subject_id', name='calendar_subjects_calendar_course_id_subject_id_key'),
        Index('idx_calendar_subjects_calendar_course_id', 'calendar_course_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    calendar_course_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))

    calendar_course: Mapped['CalendarCourses'] = relationship('CalendarCourses', back_populates='calendar_subjects')
    subject: Mapped['Subjects'] = relationship('Subjects', back_populates='calendar_subjects')


class TimetableEvents(Base):
    __tablename__ = 'timetable_events'
    __table_args__ = (
        ForeignKeyConstraint(['classroom_id'], ['classrooms.id'], ondelete='SET NULL', name='timetable_events_classroom_id_fkey'),
        ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE', name='timetable_events_subject_id_fkey'),
        PrimaryKeyConstraint('id', name='timetable_events_pkey'),
        Index('idx_timetable_events_hash', 'content_hash'),
        Index('idx_timetable_events_start', 'start_datetime'),
        Index('idx_timetable_events_subject_id', 'subject_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    start_datetime: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    end_datetime: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    is_remote: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    professor: Mapped[Optional[str]] = mapped_column(String(255))
    module_code: Mapped[Optional[str]] = mapped_column(String(50))
    credits: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(4, 1))
    classroom_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    teams_link: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    group_id: Mapped[Optional[str]] = mapped_column(String(50))

    classroom: Mapped[Optional['Classrooms']] = relationship('Classrooms', back_populates='timetable_events')
    subject: Mapped['Subjects'] = relationship('Subjects', back_populates='timetable_events')
    calendar_events: Mapped[list['CalendarEvents']] = relationship('CalendarEvents', back_populates='timetable_event')


class CalendarEvents(Base):
    __tablename__ = 'calendar_events'
    __table_args__ = (
        ForeignKeyConstraint(['calendar_id'], ['calendar_links.id'], ondelete='CASCADE', name='calendar_events_calendar_id_fkey'),
        ForeignKeyConstraint(['timetable_event_id'], ['timetable_events.id'], ondelete='CASCADE', name='calendar_events_timetable_event_id_fkey'),
        PrimaryKeyConstraint('id', name='calendar_events_pkey'),
        UniqueConstraint('calendar_id', 'timetable_event_id', name='calendar_events_calendar_id_timetable_event_id_key'),
        Index('idx_calendar_events_calendar_id', 'calendar_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    calendar_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    timetable_event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))

    calendar: Mapped['CalendarLinks'] = relationship('CalendarLinks', back_populates='calendar_events')
    timetable_event: Mapped['TimetableEvents'] = relationship('TimetableEvents', back_populates='calendar_events')
