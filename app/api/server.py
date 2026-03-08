from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError, HTTPException

from app import version
from app.api.v1.routes import health, courses, subjects, timetable
from app.api.middleware import (
    error_handler_middleware,
    validation_exception_handler,
    http_exception_handler,
    custom_404_handler,
    custom_exception_handler
)
from app.api.exceptions import (
    ValidationError,
    NotFoundError,
    ServiceUnavailableError
)

app = FastAPI(
    title="Scraper Service",
    description="UniBo Scraper Service with hourly updates",
    version=version,
    docs_url=None,
    redoc_url=None,
)

app.middleware("http")(error_handler_middleware)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(404, custom_404_handler)
app.add_exception_handler(ValidationError, custom_exception_handler)
app.add_exception_handler(NotFoundError, custom_exception_handler)
app.add_exception_handler(ServiceUnavailableError, custom_exception_handler)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(courses.router, prefix="/api/v1", tags=["courses"])
app.include_router(subjects.router, prefix="/api/v1", tags=["subjects"])
app.include_router(timetable.router, prefix="/api/v1", tags=["timetable"])
