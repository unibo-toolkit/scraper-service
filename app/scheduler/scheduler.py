import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app import config
from app.scheduler.jobs import update_courses_cache, update_timetables, cleanup_stale_events
from app.utils.custom_logger import CustomLogger

logger = CustomLogger("Scheduler")

scheduler = AsyncIOScheduler(timezone=config.scheduler.timezone)


def setup_scheduler():
    scheduler.add_job(
        update_courses_cache,
        trigger=IntervalTrigger(
            seconds=config.scheduler.update_courses_interval_seconds,
            timezone=config.scheduler.timezone
        ),
        id="update_courses_cache",
        name="Update Courses Cache",
        replace_existing=True,
        next_run_time=datetime.datetime.now(tz=scheduler.timezone)
    )

    scheduler.add_job(
        update_timetables,
        trigger=IntervalTrigger(
            seconds=config.scheduler.update_timetables_interval_seconds,
            timezone=config.scheduler.timezone
        ),
        id="update_timetables",
        name="Update Timetables",
        replace_existing=True,
        next_run_time=datetime.datetime.now(tz=scheduler.timezone) + datetime.timedelta(minutes=5)
    )

    scheduler.add_job(
        cleanup_stale_events,
        trigger=IntervalTrigger(
            seconds=config.scheduler.cleanup_stale_events_interval_seconds,
            timezone=config.scheduler.timezone
        ),
        id="cleanup_stale_events",
        name="Cleanup Stale Events",
        replace_existing=True,
        next_run_time=datetime.datetime.now(tz=scheduler.timezone) + datetime.timedelta(minutes=10)
    )

    logger.info("scheduler configured with all jobs", timezone=config.scheduler.timezone)

    jobs = scheduler.get_jobs()
    for job in jobs:
        if hasattr(job, 'next_run_time'):
            logger.info("scheduled job", name=job.name, next_run=str(job.next_run_time))
        else:
            logger.info("scheduled job", name=job.name, trigger=str(job.trigger))


def start_scheduler():
    setup_scheduler()
    scheduler.start()
    logger.info("scheduler started")

    all_jobs = scheduler.get_jobs()
    logger.info("total scheduled jobs", count=len(all_jobs))
    for job in all_jobs:
        logger.debug("active job", id=job.id, name=job.name)


def stop_scheduler():
    scheduler.shutdown()
    logger.info("scheduler stopped")
