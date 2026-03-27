from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
import hashlib
import json

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

    timetable_data = await fetch_timetable(
        course.url, curriculum.code, curriculum.label, curriculum.academic_year
    )

    new_hash = timetable_data.get("content_hash")
    if not force_update and curriculum.timetable_hash == new_hash:
        logger.info(
            "timetable unchanged, skipping update",
            course_id=str(course.id),
            curriculum_id=str(curriculum.id),
        )

        existing_subjects = await db_ops.get_subjects_by_curriculum(curriculum.id, active_only=active_only)
        return [
            {
                "id": str(s.id),
                "title": s.title,
                "module_code": s.module_code,
                "credits": s.credits,
                "professor": s.professor,
                "group_id": s.group_id,
            }
            for s in existing_subjects
        ]

    subjects_map = {}
    classrooms_map = {}

    for event in timetable_data.get("events", []):
        subject_key = (event.get("title"), event.get("module_code"), event.get("professor"))

        if subject_key not in subjects_map:
            subjects_map[subject_key] = {
                "curriculum_id": curriculum.id,
                "title": event.get("title"),
                "professor": event.get("professor"),
                "credits": event.get("cfu"),
                "module_code": event.get("module_code"),
                "group_id": event.get("group_id"),
            }

        location = event.get("location")
        if location:
            location_key = (location, event.get("address"))
            if location_key not in classrooms_map:
                classrooms_map[location_key] = {
                    "name": location,
                    "address": event.get("address"),
                    "latitude": event.get("latitude"),
                    "longitude": event.get("longitude"),
                }

    saved_classrooms = {}
    for classroom_data in classrooms_map.values():
        classroom = await db_ops.upsert_classroom(classroom_data)
        saved_classrooms[(classroom.name, classroom.address)] = classroom

    subjects = list(subjects_map.values())
    await db_ops.upsert_subjects(subjects)

    active_keys = [
        (s["title"], s.get("module_code"), s.get("professor"))
        for s in subjects
    ]
    await db_ops.mark_inactive_subjects(curriculum.id, active_keys)

    existing_subjects = await db_ops.get_subjects_by_curriculum(curriculum.id, active_only=False)
    subject_mapping = {(s.title, s.module_code, s.professor): s for s in existing_subjects}

    timetable_events = []
    for event in timetable_data.get("events", []):
        subject_key = (event.get("title"), event.get("module_code"), event.get("professor"))
        subject = subject_mapping.get(subject_key)
        if not subject:
            continue

        location = event.get("location")
        location_key = (location, event.get("address")) if location else None
        classroom = saved_classrooms.get(location_key) if location_key else None

        timetable_events.append(
            {
                "subject_id": subject.id,
                "title": event.get("title"),
                "start_datetime": event.get("start_time"),
                "end_datetime": event.get("end_time"),
                "professor": event.get("professor"),
                "classroom_id": classroom.id if classroom else None,
                "teams_link": event.get("teams_link"),
                "is_remote": event.get("is_remote", False),
                "notes": event.get("notes"),
                "module_code": event.get("module_code"),
                "credits": event.get("cfu"),
                "group_id": event.get("group_id"),
                "content_hash": compute_event_hash(event),
            }
        )

    await db_ops.bulk_insert_timetable_events(timetable_events)

    await db_ops.update_curriculum_timetable_hash(curriculum.id, new_hash)
    logger.info(
        "updated timetable hash", course_id=str(course.id), curriculum_id=str(curriculum.id)
    )

    await session.commit()

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


def compute_event_hash(event: Dict) -> str:
    fields = {
        "title": event.get("title"),
        "start": event.get("start_time"),
        "end": event.get("end_time"),
        "professor": event.get("professor"),
        "location": event.get("location"),
        "is_remote": event.get("is_remote", False),
    }
    return hashlib.sha256(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()
