import json
from typing import Optional, List, Dict
from datetime import datetime, UTC

from app.utils.redis_client import redis_client
from app.utils.custom_logger import CustomLogger
from app import config


async def get_cached_courses(logger: Optional[CustomLogger] = None) -> Optional[Dict]:
    if not logger:
        logger = CustomLogger("cache")

    try:
        data = await redis_client.redis.get("courses:full")
        if data:
            logger.debug("cache hit for courses")
            return json.loads(data)
        logger.debug("cache miss for courses")
    except Exception as e:
        logger.warning("failed to get cached courses", error=str(e))
    return None


async def set_cached_courses(courses: List[Dict], logger: Optional[CustomLogger] = None):
    if not logger:
        logger = CustomLogger("cache")

    try:
        cache_data = {
            "items": courses,
            "cached_at": datetime.now(UTC).isoformat(),
            "ttl": config.scraper.cache_courses_list_ttl
        }

        await redis_client.redis.setex(
            "courses:full",
            config.scraper.cache_courses_list_ttl,
            json.dumps(cache_data)
        )
        logger.info("cached courses", count=len(courses))

    except Exception as e:
        logger.warning("failed to cache courses", error=str(e))


async def get_cached_subjects(
    cache_key: str,
    logger: Optional[CustomLogger] = None
) -> Optional[List[dict]]:
    if not logger:
        logger = CustomLogger("cache:subjects")

    try:
        data = await redis_client.redis.get(cache_key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning("cache get failed", error=str(e))

    return None


async def set_cached_subjects(
    cache_key: str,
    subjects: List[dict],
    logger: Optional[CustomLogger] = None
):
    if not logger:
        logger = CustomLogger("cache:subjects")

    try:
        ttl = config.scraper.cache_timetable_ttl
        await redis_client.redis.setex(
            cache_key,
            ttl,
            json.dumps(subjects)
        )
    except Exception as e:
        logger.warning("cache set failed", error=str(e))
