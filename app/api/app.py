from fastapi import FastAPI

from app import version
from app.api.v1.routes import health, courses

app = FastAPI(
    title="Scraper Service",
    description="UniBo Scraper Service with hourly updates",
    version=version,
    docs_url=None,
    redoc_url=None,
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(courses.router, prefix="/api/v1", tags=["courses"])
