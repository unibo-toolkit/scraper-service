from fastapi import Request
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.exceptions import (
    ValidationError,
    NotFoundError,
    ServiceUnavailableError,
    create_error_response,
)
from app.utils.custom_logger import CustomLogger


async def error_handler_middleware(request: Request, call_next):
    logger = CustomLogger("api:middleware")

    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(
            "unhandled exception in middleware",
            path=str(request.url),
            method=request.method,
            error=str(e),
        )

        return create_error_response(
            status_code=500,
            error="internal_server_error",
            message="An unexpected error occurred",
        )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger = CustomLogger("api:validation_error")

    errors = []
    for error in exc.errors():
        field = ".".join(str(x) for x in error["loc"][1:])
        errors.append(f"{field}: {error['msg']}")

    message = "Invalid request parameters: " + "; ".join(errors)

    logger.warning("validation error", path=str(request.url), errors=errors)

    return create_error_response(
        status_code=400, error="validation_error", message=message
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    logger = CustomLogger("api:http_exception")

    logger.info(
        "http exception", path=str(request.url), status_code=exc.status_code, detail=exc.detail
    )

    error_mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        422: "unprocessable_entity",
        429: "too_many_requests",
        500: "internal_server_error",
        502: "bad_gateway",
        503: "service_unavailable",
        504: "gateway_timeout",
    }

    error_type = error_mapping.get(exc.status_code, "http_error")

    return create_error_response(
        status_code=exc.status_code, error=error_type, message=exc.detail
    )


async def custom_404_handler(request: Request, _: StarletteHTTPException):
    logger = CustomLogger("api:404")

    logger.info("endpoint not found", path=str(request.url), method=request.method)

    return create_error_response(
        status_code=404,
        error="not_found",
        message=f"Endpoint {request.method} {request.url.path} not found",
    )


async def custom_exception_handler(request: Request, exc: Exception):
    logger = CustomLogger("api:custom_exception")

    if isinstance(exc, ValidationError):
        logger.warning("custom validation error", path=str(request.url), message=exc.message)

        return create_error_response(
            status_code=exc.status_code,
            error="validation_error",
            message=exc.message,
        )

    elif isinstance(exc, NotFoundError):
        logger.info("resource not found", path=str(request.url), message=exc.message)

        return create_error_response(
            status_code=exc.status_code, error="not_found", message=exc.message
        )

    elif isinstance(exc, ServiceUnavailableError):
        logger.error("service unavailable", path=str(request.url), message=exc.message)

        return create_error_response(
            status_code=exc.status_code,
            error="service_unavailable",
            message=exc.message,
        )

    logger.error("unknown custom exception", path=str(request.url), error=str(exc))

    return create_error_response(
        status_code=500,
        error="internal_server_error",
        message="An unexpected error occurred",
    )
