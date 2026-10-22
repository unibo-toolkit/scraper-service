import json
from typing import Any, Optional

from app.utils.custom_logger import CustomLogger
from app.utils.redis_client import redis_client


class JsonCache:
    """
    Redis access that never breaks the caller: a cache miss and a cache
    failure are the same thing for every consumer.
    """

    def __init__(self, logger: CustomLogger):
        self.logger = logger

    async def get(self, key: str) -> Optional[Any]:
        try:
            payload = await redis_client.redis.get(key)
        except Exception as e:
            self.logger.warning("cache get failed", key=key, error=str(e))
            return None

        return json.loads(payload) if payload else None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            await redis_client.redis.setex(key, ttl, json.dumps(value))
        except Exception as e:
            self.logger.warning("cache set failed", key=key, error=str(e))

    async def delete(self, key: str) -> None:
        try:
            await redis_client.redis.delete(key)
        except Exception as e:
            self.logger.warning("cache delete failed", key=key, error=str(e))
