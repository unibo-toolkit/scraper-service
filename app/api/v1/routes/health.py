from fastapi import APIRouter
from sqlalchemy import text

from app import version
from app.utils.database import engine
from app.utils.redis_client import redis_client

router = APIRouter()


@router.get("/health")
async def health_check():
    db_status = "healthy"
    redis_status = "healthy"
    overall_status = "healthy"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        overall_status = "unhealthy"

    try:
        if redis_client.redis:
            await redis_client.redis.ping()
        else:
            redis_status = "unhealthy: not connected"
            overall_status = "unhealthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "version": version,
        "database": db_status,
        "redis": redis_status,
        "details": {"service": "scraper-service"},
    }
