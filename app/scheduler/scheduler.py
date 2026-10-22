from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app import config
from app.scheduler.jobs import cleanup_stale_events, update_courses_cache, update_timetables
from app.utils.custom_logger import CustomLogger

logger = CustomLogger("Scheduler")

scheduler = AsyncIOScheduler(timezone=config.scheduler.timezone)


@dataclass(frozen=True, slots=True)
class Job:
    """
    A recurring job as the scheduler registers it.

    Attributes:
        func: Coroutine to run. Takes no arguments: the job builds its own
            session and logger.
        id: Stable id, so a restart replaces the job instead of doubling it.
        name: Human readable name used in the logs.
        interval_seconds: Delay between two runs.
        initial_delay: Offset of the first run after startup, used to spread the
            jobs out instead of hitting the site with all of them at once.
    """

    func: Callable[[], Awaitable[None]]
    id: str
    name: str
    interval_seconds: int
    initial_delay: timedelta = field(default=timedelta())


JOBS = (
    Job(
        update_courses_cache,
        "update_courses_cache",
        "Update Courses Cache",
        config.scheduler.update_courses_interval_seconds,
    ),
    Job(
        update_timetables,
        "update_timetables",
        "Update Timetables",
        config.scheduler.update_timetables_interval_seconds,
        timedelta(minutes=5),
    ),
    Job(
        cleanup_stale_events,
        "cleanup_stale_events",
        "Cleanup Stale Events",
        config.scheduler.cleanup_stale_events_interval_seconds,
        timedelta(minutes=10),
    ),
)


def setup_scheduler() -> None:
    now = datetime.now(tz=scheduler.timezone)

    for job in JOBS:
        scheduler.add_job(
            job.func,
            trigger=IntervalTrigger(
                seconds=job.interval_seconds, timezone=config.scheduler.timezone
            ),
            id=job.id,
            name=job.name,
            replace_existing=True,
            next_run_time=now + job.initial_delay,
        )

    logger.info("scheduler configured", timezone=config.scheduler.timezone, jobs=len(JOBS))


def start_scheduler() -> None:
    setup_scheduler()
    scheduler.start()

    for job in scheduler.get_jobs():
        logger.info("scheduled job", name=job.name, next_run=str(job.next_run_time))


def stop_scheduler() -> None:
    scheduler.shutdown()
    logger.info("scheduler stopped")
