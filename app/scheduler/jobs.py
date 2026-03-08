import asyncio
from typing import Dict, List, Optional

from app.models import Courses
from app.utils.custom_logger import CustomLogger
from app.utils.database import AsyncSessionLocal, AsyncSession
from app.core import scraper, cache
from app.core.database import DatabaseOperations
from app.core.subjects import fetch_and_save_subjects
from app import config


async def _resolve_results(
    courses_it: List[Dict],
    english_titles: Dict,
    db: DatabaseOperations,
    session: AsyncSession,
    logger: Optional[CustomLogger] = None,
):
    if not logger:
        logger = CustomLogger("resolve_results")

    for course_data in courses_it:
        course_data["title_en"] = english_titles.get(course_data["unibo_id"], None)

        course = await db.upsert_course(course_data)

        if course_data.get("curricula"):
            curricula_to_save = [
                {"code": curr["code"], "label": curr["label"], "academic_year": year}
                for year in range(1, course_data["duration_years"] + 1)
                for curr in course_data["curricula"]
            ]
            await db.upsert_curricula(course.id, curricula_to_save)

            active_codes = [
                (curr["code"], year)
                for year in range(1, course_data["duration_years"] + 1)
                for curr in course_data["curricula"]
            ]
            await db.mark_inactive_curricula(course.id, active_codes)

    await session.commit()
    logger.debug("resolved and saved courses", count=len(courses_it))


def _format_courses_for_cache(courses: List[Courses]) -> List[Dict]:
    formatted_courses = []
    for course in courses:
        formatted_course = {
            "id": str(course.id),
            "unibo_id": course.unibo_id,
            "title_it": course.title_it,
            "title_en": course.title_en,
            "course_type": course.course_type,
            "campus": course.campus,
            "languages": course.languages or [],
            "duration_years": course.duration_years,
            "url": course.url,
            "area": course.area,
            "curricula": sorted(
                [
                    {
                        "id": str(curr.id),
                        "code": curr.code,
                        "label": curr.label,
                        "academic_year": curr.academic_year,
                    }
                    for curr in (course.curricula or [])
                ],
                key=lambda x: (x.get("academic_year", 0)),
            ),
        }
        formatted_courses.append(formatted_course)
    return formatted_courses


async def update_courses_cache(logger: Optional[CustomLogger] = None):
    if not logger:
        logger = CustomLogger("scheduler:update_courses_cache")

    logger.info("starting courses cache update")

    async with AsyncSessionLocal() as session:
        try:
            db = DatabaseOperations(session, logger=logger)

            courses_it = await scraper.fetch_courses_italian(logger=logger)

            english_titles = await scraper.fetch_courses_english(logger=logger)

            await _resolve_results(courses_it, english_titles, db, session, logger=logger)

            current_unibo_ids = [c["unibo_id"] for c in courses_it]
            marked_inactive = await db.mark_inactive_courses(current_unibo_ids)
            if marked_inactive > 0:
                logger.info("marked inactive courses", count=marked_inactive)

            courses = await db.get_all_courses(with_curricula=True)

            formated_courses = _format_courses_for_cache(courses)
            await cache.set_cached_courses(formated_courses, logger=logger)
            logger.info("cashing courses completed")
        except Exception as e:
            logger.error("failed to update courses cache", error=str(e))
            raise


async def update_timetables(logger: Optional[CustomLogger] = None):
    if not logger:
        logger = CustomLogger("scheduler:update_timetables")

    logger.info("starting timetables update")

    async with AsyncSessionLocal() as session:
        try:
            db_ops = DatabaseOperations(session, logger=logger)

            active_curricula = await db_ops.get_active_curricula()
            logger.info("found active curricula", count=len(active_curricula))

            if not active_curricula:
                logger.info("no active curricula to update")
                return

            updated_count = 0
            skipped_count = 0
            error_count = 0

            for idx, curriculum in enumerate(active_curricula):
                try:
                    logger.debug(
                        "processing curriculum",
                        curriculum_id=str(curriculum.id),
                        code=curriculum.code,
                    )

                    course = curriculum.course

                    if not course or not course.url:
                        logger.warning(
                            "no course url for curriculum", curriculum_id=str(curriculum.id)
                        )
                        error_count += 1
                        continue

                    subjects = await fetch_and_save_subjects(session, course, curriculum, logger)

                    cache_key = f"subjects:{curriculum.id}"
                    await cache.set_cached_subjects(cache_key, subjects, logger)

                    if curriculum.timetable_hash:
                        updated_count += 1
                    else:
                        skipped_count += 1

                except Exception as e:
                    logger.error(
                        "failed to update timetable", curriculum_id=str(curriculum.id), error=str(e)
                    )
                    error_count += 1
                    continue

                if idx < len(active_curricula) - 1:
                    await asyncio.sleep(config.scraper.delay_between_timetable_requests)

            deleted_classrooms = await db_ops.cleanup_unused_classrooms()
            if deleted_classrooms > 0:
                logger.info("deleted unused classrooms", count=deleted_classrooms)

            await session.commit()

            logger.info(
                "timetables update completed",
                updated=updated_count,
                skipped=skipped_count,
                errors=error_count,
            )

        except Exception as e:
            logger.error("failed to update timetables", error=str(e))
            await session.rollback()
            raise
