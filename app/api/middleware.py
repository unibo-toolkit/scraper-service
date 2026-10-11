import logging

from fastapi import Request
from fastapi.exceptions import HTTPException, RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.exceptions import HTTP_ERROR_CODES, AppError, create_error_response
from app.utils.custom_logger import CustomLogger

# How loudly each class of failure is reported.
APP_ERROR_LEVELS = {400: logging.WARNING, 404: logging.INFO}


async def error_handler_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        CustomLogger("api:middleware").error(
            "unhandled exception in middleware",
            path=str(request.url),
            method=request.method,
            error=str(e),
        )
        return create_error_response(500, "internal_server_error", "An unexpected error occurred")


async def app_exception_handler(request: Request, exc: AppError):
    logger = CustomLogger("api:app_error")
    level = APP_ERROR_LEVELS.get(exc.status_code, logging.ERROR)

    logger.log(level, exc.code, path=str(request.url), message=exc.message)
    return create_error_response(exc.status_code, exc.code, exc.message)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        f"{'.'.join(str(part) for part in error['loc'][1:])}: {error['msg']}"
        for error in exc.errors()
    ]

    CustomLogger("api:validation_error").warning(
        "validation error", path=str(request.url), errors=errors
    )
    return create_error_response(
        400, "validation_error", "Invalid request parameters: " + "; ".join(errors)
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    CustomLogger("api:http_exception").info(
        "http exception", path=str(request.url), status_code=exc.status_code, detail=exc.detail
    )
    return create_error_response(
        exc.status_code, HTTP_ERROR_CODES.get(exc.status_code, "http_error"), exc.detail
    )


async def custom_404_handler(request: Request, _: StarletteHTTPException):
    CustomLogger("api:404").info(
        "endpoint not found", path=str(request.url), method=request.method
    )
    return create_error_response(
        404, "not_found", f"Endpoint {request.method} {request.url.path} not found"
    )
