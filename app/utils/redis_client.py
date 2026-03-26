from typing import Optional

from redis import asyncio as aioredis

from app import config
from app.utils.custom_logger import CustomLogger

logger = CustomLogger("RedisClient")


class RedisClient:
    def __init__(self) -> None:
        self.redis: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        try:
            self.redis = aioredis.from_url(
                config.redis.url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.redis.ping()
            logger.info("redis connected", url=config.redis.url)
        except Exception as e:
            logger.error("redis connection failed", error=str(e))
            raise

    async def disconnect(self) -> None:
        if self.redis:
            await self.redis.close()
            logger.info("redis disconnected")


redis_client = RedisClient()
