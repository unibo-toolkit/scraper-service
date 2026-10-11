from datetime import datetime
from typing import List, Dict, Tuple, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession
import hashlib
import json

from unibo_toolkit.models import Classroom, TimetableEvent

from app.models.generated import Courses, Curricula
from app.core.database import DatabaseOperations
from app.core.scraper import fetch_timetable
from app.utils.custom_logger import CustomLogger


async def fetch_and_save_subjects(
    session: AsyncSession,
    course: Courses,
    curriculum: Curricula,
    logger: CustomLogger,
    force_update: bool = False,
    active_only: bool = True,
) -> List[Dict]:
    db_ops = DatabaseOperations(session, logger)

    # fetch new data with scraper
    timetable_data = await fetch_timetable(
        course.url, curriculum.code, curriculum.label, curriculum.academic_year
    )

    new_hash = timetable_data.content_hash
    if not force_update and curriculum.timetable_hash == new_hash:
        logger.info(
            "timetable unchanged, skipping update",
            course_id=str(course.id),
            curriculum_id=str(curriculum.id),
        )

        # update hash in DB even if unchanged to update updated_at timestamp
        await db_ops.update_curriculum_timetable_hash(curriculum.id, new_hash)
        await session.commit()

        # return existing subjects without changes
        existing_subjects = await db_ops.get_subjects_by_curriculum(curriculum.id, active_only=active_only)
        return [  # TODO use dataclasses
            {
                "id": str(subject.id),
                "title": subject.title,
                "module_code": subject.module_code,
                "credits": subject.credits,
                "professor": subject.professor,
                "group_id": subject.group_id,
            }
            for subject in existing_subjects
        ]

    subjects_map: Dict[Tuple[str, str, Optional[str]], TimetableEvent] = {}
    classrooms_map: Dict[Tuple[str, str], Classroom] = {}

    # update events timezone and build maps for subjects and classrooms to identify unique entries
    # subject uses (title, module_code, professor) as key
    # classroom uses (name, address) as key
    for event in timetable_data.events:
        # change events TZ to Europe/Rome
        event.start = __update_timezone(event.start)
        event.end = __update_timezone(event.end)

        subject_key: Tuple[str, str, Optional[str]] = (event.title, event.module_code, event.professor)
        if subject_key not in subjects_map:
            subjects_map[subject_key] = event

        # if there is no title for the classroom, we skip it. This is to avoid creating classrooms with empty names.
        if event.primary_classroom and event.primary_classroom.title:
            classroom_key = (event.primary_classroom.title, event.primary_classroom.address)
            if classroom_key not in classrooms_map:
                classrooms_map[classroom_key] = event.primary_classroom

    saved_classrooms = {}
    for classroom_data in classrooms_map.values():
        classroom = await db_ops.upsert_classroom(classroom_data)
        saved_classrooms[(classroom.name, classroom.address)] = classroom

    # we uses events data to upsert subjects
    events = list(subjects_map.values())
    await db_ops.upsert_subjects(curriculum.id, events)

    # mark subjects as inactive if they are not present in the new timetable data
    active_keys = list(subjects_map.keys())
    await db_ops.mark_inactive_subjects(curriculum.id, active_keys)

    # we fetch all subjects for the curriculum, including inactive ones, to build a mapping for the next step
    existing_subjects = await db_ops.get_subjects_by_curriculum(curriculum.id, active_only=False)
    subject_mapping = {(s.title, s.module_code, s.professor): s for s in existing_subjects}
    all_subject_ids = [s.id for s in existing_subjects]

    # we build the timetable events data to upsert into the database
    timetable_events = []
    for event in timetable_data.events:
        subject_key = (event.title, event.module_code, event.professor)
        subject = subject_mapping.get(subject_key)
        if not subject:
            continue

        event_classroom = event.primary_classroom if event.primary_classroom else None
        classroom_key = (event_classroom.title, event_classroom.address) if event_classroom else None
        classroom = saved_classrooms.get(classroom_key) if classroom_key else None

        timetable_events.append(
            {  # TODO refactor to object
                "subject_id": subject.id,
                "title": event.title,
                "start_datetime": event.start,
                "end_datetime": event.end,
                "professor": event.professor,
                "classroom_id": classroom.id if classroom else None,
                "teams_link": event.teams_link,
                "is_remote": event.is_remote,
                "notes": event.notes,
                "module_code": event.module_code,
                "credits": event.credits,
                "group_id": event.group_id,
                "content_hash": __compute_event_hash(event),
            }
        )

    await db_ops.sync_timetable_events(all_subject_ids, timetable_events)

    # update the curriculum timetable hash in the database
    await db_ops.update_curriculum_timetable_hash(curriculum.id, new_hash)
    logger.info(
        "updated timetable hash", course_id=str(course.id), curriculum_id=str(curriculum.id)
    )

    await session.commit()

    # return the subjects for the curriculum, filtered by active_only if specified
    result_subjects = await db_ops.get_subjects_by_curriculum(curriculum.id, active_only=active_only)
    return [
        {
            "id": str(s.id),
            "title": s.title,
            "module_code": s.module_code,
            "credits": s.credits,
            "professor": s.professor,
            "group_id": s.group_id,
        }
        for s in result_subjects
    ]


def __compute_event_hash(event: TimetableEvent) -> str:
    fields = {
        "title": event.title,
        "start": event.start,
        "end": event.end,
        "professor": event.professor,
        "location": event.primary_classroom.title if event.primary_classroom else None,
        "is_remote": event.is_remote,
    }
    return hashlib.sha256(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()


def __update_timezone(dt: datetime) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("Europe/Rome"))
    return dt
