from pydantic import BaseModel
from fastapi.responses import JSONResponse


class ErrorResponse(BaseModel):
    error: str
    message: str
    status_code: int


class ValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        self.status_code = 400
        super().__init__(message)


class NotFoundError(Exception):
    def __init__(self, message: str = "Resource not found"):
        self.message = message
        self.status_code = 404
        super().__init__(message)


class ServiceUnavailableError(Exception):
    def __init__(self, message: str = "Service temporarily unavailable"):
        self.message = message
        self.status_code = 503
        super().__init__(message)


def create_error_response(
    status_code: int,
    error: str,
    message: str
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=error,
            message=message,
            status_code=status_code
        ).model_dump()
    )
