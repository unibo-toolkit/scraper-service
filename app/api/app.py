from fastapi import FastAPI

from app import version
from app.api.v1.routes import health

app = FastAPI(
    title="Scraper Service",
    description="UniBo Scraper Service with hourly updates",
    version=version,
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])


@app.get("/")
async def root() -> dict:
    return {
        "service": "scraper-service",
        "version": version,
        "status": "running",
    }
