import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple, Set
from uuid import UUID
from zoneinfo import ZoneInfo

SubjectKey = Tuple[str, Optional[str], Optional[str]]
ClassroomKey = Tuple[str, Optional[str]]

ROME_TZ = ZoneInfo("Europe/Rome")

# Slot width used to group lessons into a family. Real slots sit 10 minutes
# apart at the closest and 120 at the median, so a quarter-hour absorbs the
# jitter of the feed without merging neighbors.
FAMILY_SLOT_MINUTES = 15


@dataclass(frozen=True, slots=True)
class Classroom:
    """
    A teaching location as the timetable feed reports it.

    Attributes:
        name: Room title, e.g. "Aula 2.1". The only thing identifying a room,
            so nameless ones are never stored.
        address: Street address. Missing for a part of the rooms, which is why
            the unique constraint on (name, address) does not cover every row.
        latitude: Latitude, None when the feed carries no coordinates.
        longitude: Longitude, None when the feed carries no coordinates.
        id: Database id. None for a room that has not been stored yet.
    """

    name: str
    address: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    id: Optional[UUID] = None

    @property
    def key(self) -> ClassroomKey:
        """
        Natural key of the room, matching the classrooms_name_address_key
        constraint.

        Returns:
            (name, address) pair, used to look the stored id up.
        """
        return self.name, self.address


@dataclass(frozen=True, slots=True)
class Subject:
    """
    A teaching module of one curriculum, derived from the events that mention it.

    The feed has no subject list: subjects are what is left after grouping the
    events by (title, module_code, professor).

    Attributes:
        title: Subject name as printed in the feed, uppercased and unformatted.
        module_code: UniBo module code (cod_modulo). None for some events.
        professor: Teacher name. Part of the identity: the same module taught by
            two people counts as two subjects.
        credits: CFU, whole number here (the subjects column is SMALLINT).
        group_id: Stream the subject belongs to, e.g. "CL.A". None when the
            subject is not split into streams.
        is_active: False once the subject stopped appearing in the feed. Such
            rows are kept because events may still reference them.
        id: Database id. None for a subject that has not been stored yet.
    """

    title: str
    module_code: Optional[str] = None
    professor: Optional[str] = None
    credits: Optional[int] = None
    group_id: Optional[str] = None
    is_active: bool = True
    id: Optional[UUID] = None

    @property
    def key(self) -> SubjectKey:
        """
        Identity of the subject inside its curriculum.

        Returns:
            (title, module_code, professor) triple.
        """
        return self.title, self.module_code, self.professor


@dataclass(frozen=True, slots=True)
class Slot:
    """
    A weekly position: local weekday plus the start time rounded to the family
    grid. Worth storing next to a user exclusion, so the family can be found
    again after the timetable moves it.

    Attributes:
        weekday: Monday is 0, as datetime.weekday() reports it.
        start_minutes: Minutes since local midnight, a multiple of
            FAMILY_SLOT_MINUTES.
    """

    weekday: int
    start_minutes: int

    @property
    def start_time(self) -> str:
        """
        Returns:
            Start of the slot as "HH:MM", ready to show to a user.
        """
        return f"{self.start_minutes // 60:02d}:{self.start_minutes % 60:02d}"


@dataclass(frozen=True, slots=True)
class Event:
    """
    A single lesson: one row of the timetable, scraped or stored.

    The same class covers both directions, so the identity fields are optional:
    a scraped event has no `id` yet, a stored one always has.

    Attributes:
        title: Subject name the event belongs to.
        start: Start time, always timezone-aware in Europe/Rome.
        end: End time, always timezone-aware in Europe/Rome.
        professor: Teacher name.
        module_code: UniBo module code (cod_modulo).
        credits: CFU as Decimal, matching the NUMERIC(4,1) column.
        group_id: Stream of the event, taken from cod_sdoppiamento only.
        classroom: Room the lesson happens in. None when the feed gives none,
            or gives one without a name.
        location: Raw room name from the feed, kept apart from `classroom`
            because content_hash is built on it. See content_hash.
        is_remote: True for online lessons, which usually carry a teams_link.
        teams_link: Microsoft Teams url of a remote lesson.
        notes: Free-text note of the feed.
        id: Database id. None for a scraped event.
        subject_id: Owning subject. None for a scraped event, since subjects are
            resolved only while writing.
    """

    title: str
    start: datetime
    end: datetime
    professor: Optional[str] = None
    module_code: Optional[str] = None
    credits: Optional[Decimal] = None
    group_id: Optional[str] = None
    classroom: Optional[Classroom] = None
    location: Optional[str] = None
    is_remote: bool = False
    teams_link: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[UUID] = None
    subject_id: Optional[UUID] = None

    FAMILY_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")

    @property
    def subject_key(self) -> SubjectKey:
        """
        Key of the subject this event belongs to.

        Returns:
            (title, module_code, professor) triple, matching Subject.key.
        """
        return self.title, self.module_code, self.professor

    @property
    def content_hash(self) -> str:
        """
        Identity of an event as seen on the UniBo site.

        Built from `location`, the raw room name of the feed, and not from
        `classroom`, which is already normalized: the hash must not move when
        normalization rules do. Changing the field set invalidates every row of
        timetable_events, so the set is fixed: the columns left out of it are
        refreshed in place by EventsOperations.sync instead.

        Returns:
            Hex sha256 over title, start, end, professor, location and is_remote.
        """
        fields = {
            "title": self.title,
            "start": self.start,
            "end": self.end,
            "professor": self.professor,
            "location": self.location,
            "is_remote": self.is_remote,
        }
        payload = json.dumps(fields, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    def as_subject(self) -> Subject:
        """
        Builds the subject this event implies.

        Returns:
            Subject carrying the identity fields plus credits and group taken
            from this event.
        """
        return Subject(
            title=self.title,
            module_code=self.module_code,
            professor=self.professor,
            credits=int(self.credits) if self.credits is not None else None,
            group_id=self.group_id,
        )

    @property
    def slot(self) -> Slot:
        """
        Slot a lesson starting at the given moment to.
        Returns:
            Slot with the local weekday and the start minute rounded down to
            the family grid.
        """
        return self.slot_of(self.start)

    @property
    def family_hash(self) -> str:
        """
        Identity of a family of events, i.e. every lesson of this subject that
        recurs in the same weekly slot.

        Duration is left out on purpose: a lesson that runs short once is still
        the same lesson, and keeping it split 210 real slots in two. The slot is
        read in local time, otherwise a family breaks apart at every DST change.

        Returns:
            Hex sha256 over subject_id, group_id, weekday and start slot.
        """
        if not self.subject_id:
            raise ValueError("Cannot compute family_hash without subject_id")

        slot = self.slot
        fields = {
            "subject_id": self.subject_id,
            "group_id": self.group_id,
            "weekday": slot.weekday,
            "start_bucket": slot.start_minutes // FAMILY_SLOT_MINUTES,
        }
        payload = json.dumps(fields, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def slot_of(start: datetime) -> Slot:
        """
        Weekly slot this lesson sits in, in local time.

        Returns:
            Slot with the local weekday and the start minute rounded down to
            the family grid.
        """
        start = start.astimezone(ROME_TZ)
        minutes = start.hour * 60 + start.minute
        return Slot(weekday=start.weekday(), start_minutes=minutes - minutes % FAMILY_SLOT_MINUTES)

    @staticmethod
    def validate_family_hash(family_hash: str) -> None:
        """
        Validates a single family_hash, raising ValueError if invalid.

        Args:
            family_hash: family_hash to validate.
        """
        if not Event.FAMILY_HASH_PATTERN.match(family_hash):
            raise ValueError(f"Invalid family_hash: {family_hash}")

    @staticmethod
    def validate_family_hashes(family_hashes: List[str]) -> Set[str]:
        """
        Validates a list of family_hashes, raising ValueError on the first
        invalid one.

        Args:
            family_hashes: List of family_hashes to validate.

        Returns:
            Set of valid family_hashes.
        """
        valid: Set[str] = set()
        for family_hash in family_hashes:
            Event.validate_family_hash(family_hash)
            valid.add(family_hash)
        return valid


@dataclass(frozen=True, slots=True)
class Timetable:
    """
    One scrape of a curriculum timetable.

    Attributes:
        content_hash: Hash of the whole timetable, computed by unibo_toolkit
            over every field of every event. Compared against
            curricula.timetable_hash to decide whether anything has to be
            written at all.
        events: Every lesson of the curriculum, in feed order.
    """

    content_hash: str
    events: Sequence[Event] = field(default_factory=tuple)

    def subjects(self) -> List[Subject]:
        """
        Distinct subjects mentioned by the events.

        Credits and group of a subject come from the first event carrying its
        key, the way the pre-refactor code resolved them.

        Returns:
            One Subject per (title, module_code, professor).
        """
        unique: Dict[SubjectKey, Subject] = {}
        for event in self.events:
            unique.setdefault(event.subject_key, event.as_subject())
        return list(unique.values())

    def classrooms(self) -> List[Classroom]:
        """
        Distinct classrooms worth storing.

        Nameless rooms are left out: the name is all that identifies them and
        the column is NOT NULL.

        Returns:
            One Classroom per (name, address).
        """
        unique: Dict[ClassroomKey, Classroom] = {}
        for event in self.events:
            if event.classroom and event.classroom.name:
                unique.setdefault(event.classroom.key, event.classroom)
        return list(unique.values())


@dataclass(frozen=True, slots=True)
class Family:
    """
    A recurring lesson: every event of one subject that sits in the same weekly
    slot. This is the unit a user excludes from their calendar.

    Attributes:
        subject_id: Owning subject.
        family_hash: Value of Event.family_hash shared by every member.
        title: Subject name, taken from the latest member so a renamed subject
            shows under its current name.
        slot: Weekly position, the same for all members by construction.
        group_id: Stream of the lessons, part of the family identity.
        events: How many lessons the family holds. 1 642 of 6 480 families hold
            exactly one, so the number is worth showing to a user.
        first_at: Start of the earliest lesson.
        last_at: Start of the latest lesson.
    """

    subject_id: UUID
    family_hash: str
    title: str
    slot: Slot
    group_id: Optional[str]
    events: int
    first_at: datetime
    last_at: datetime

    @classmethod
    def of(cls, family_hash: str, events: Sequence[Event]) -> "Family":
        """
        Builds the family a group of events sharing a family_hash forms.

        Args:
            family_hash: Hash shared by the events.
            events: Members of the family, at least one.

        Returns:
            Family described by its latest member.
        """
        ordered = sorted(events, key=lambda event: event.start)
        latest = ordered[-1]

        return cls(
            subject_id=latest.subject_id,
            family_hash=family_hash,
            title=latest.title,
            slot=latest.slot,
            group_id=latest.group_id,
            events=len(ordered),
            first_at=ordered[0].start,
            last_at=latest.start,
        )


def group_families(events: Sequence[Event], only: Optional[Set[str]] = None) -> List[Family]:
    """
    Groups events into families.

    Args:
        events: Events to group, every one of them carrying a subject_id.
        only: Hashes to keep, or None for all of them. A hash matching no event
            is simply absent from the result, which is how a client learns its
            exclusion went stale.

    Returns:
        One Family per hash, ordered by weekly position.
    """
    if only is not None and not only:
        return []

    members: Dict[str, List[Event]] = {}
    for event in events:
        family_hash = event.family_hash
        if only is None or family_hash in only:
            members.setdefault(family_hash, []).append(event)

    return sorted(
        (Family.of(family_hash, group) for family_hash, group in members.items()),
        key=lambda family: (family.slot.weekday, family.slot.start_minutes),
    )
