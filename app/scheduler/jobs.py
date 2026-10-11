from contextlib import asynccontextmanager
from typing import Optional

from app.core.catalog import CourseCatalog
from app.core.timetable import TimetableSync
from app.utils.custom_logger import CustomLogger
from app.utils.database import AsyncSessionLocal


async def update_courses_cache(logger: Optional[CustomLogger] = None):
    async with _job("update_courses_cache", logger) as (session, log):
        courses = await CourseCatalog(session, log).refresh()
        log.info("courses cache updated", count=len(courses))


async def update_timetables(logger: Optional[CustomLogger] = None):
    async with _job("update_timetables", logger) as (session, log):
        report = await TimetableSync(session, log).sync_subscribed()
        log.info(
            "timetables update completed",
            updated=report.updated,
            skipped=report.skipped,
            errors=report.errors,
        )


async def cleanup_stale_events(logger: Optional[CustomLogger] = None):
    async with _job("cleanup_stale_events", logger) as (session, log):
        deleted = await TimetableSync(session, log).cleanup_stale_events()
        log.info("stale events cleanup completed", deleted=deleted)


@asynccontextmanager
async def _job(name: str, logger: Optional[CustomLogger]):
    log = logger or CustomLogger(f"scheduler:{name}")
    log.info("job started", job=name)

    async with AsyncSessionLocal() as session:
        try:
            yield session, log
        except Exception as e:
            log.error("job failed", job=name, error=str(e))
            raise
