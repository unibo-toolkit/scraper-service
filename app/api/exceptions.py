from fastapi.responses import JSONResponse
from pydantic import BaseModel

# HTTP phrases are part of the response contract, so they are spelled out
# instead of derived from http.HTTPStatus (whose wording changes across versions).
HTTP_ERROR_CODES = {
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


class ErrorResponse(BaseModel):
    error: str
    message: str
    status_code: int


class AppError(Exception):
    status_code = 500
    code = "internal_server_error"
    default_message = "An unexpected error occurred"

    def __init__(self, message: str = ""):
        self.message = message or self.default_message
        super().__init__(self.message)


class ValidationError(AppError):
    status_code = 400
    code = "validation_error"
    default_message = "Invalid request"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    default_message = "Resource not found"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    default_message = "Service temporarily unavailable"


def create_error_response(status_code: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=error, message=message, status_code=status_code
        ).model_dump(),
    )
