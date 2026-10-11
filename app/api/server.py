from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError

from app.api.exceptions import AppError
from app.api.middleware import (
    app_exception_handler,
    custom_404_handler,
    error_handler_middleware,
    http_exception_handler,
    validation_exception_handler,
)
from app.api.v1.routes import courses, health, subjects, timetable

app = FastAPI(
    title="Scraper Service",
    description="UniBo Scraper Service with hourly updates",
    docs_url=None,
    redoc_url=None,
)

app.middleware("http")(error_handler_middleware)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(404, custom_404_handler)
app.add_exception_handler(AppError, app_exception_handler)

for router, tag in (
    (health.router, "health"),
    (courses.router, "courses"),
    (subjects.router, "subjects"),
    (timetable.router, "timetable"),
):
    app.include_router(router, prefix="/api/v1", tags=[tag])
