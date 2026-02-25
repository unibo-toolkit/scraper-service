import json
from typing import Any, Optional

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

    async def get(self, key: str) -> Optional[Any]:
        if not self.redis:
            return None

        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning("redis GET failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if not self.redis:
            return False

        try:
            serialized = json.dumps(value, ensure_ascii=False)
            if ttl:
                await self.redis.setex(key, ttl, serialized)
            else:
                await self.redis.set(key, serialized)
            return True
        except Exception as e:
            logger.warning("redis SET failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        if not self.redis:
            return False

        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.warning("redis DELETE failed", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        if not self.redis:
            return False

        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.warning("redis EXISTS failed", key=key, error=str(e))
            return False


redis_client = RedisClient()
