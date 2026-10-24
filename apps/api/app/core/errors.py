from collections.abc import Mapping
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.i18n import error_message, negotiate_language

logger = structlog.get_logger(__name__)

HTTP_STATUS_CODES = {
    401: "auth.unauthenticated",
    403: "auth.forbidden",
    404: "request.not_found",
    405: "request.method_not_allowed",
}


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any]
    request_id: str | None


class ErrorResponse(BaseModel):
    """The envelope of every non-2xx response (§4.2)."""

    error: ErrorBody


# Declared on routers so the generated TypeScript client knows the error shape.
COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Missing, expired or invalid access token"},
    403: {"model": ErrorResponse, "description": "Authenticated but not allowed"},
    409: {"model": ErrorResponse, "description": "Conflicts with existing data"},
    422: {"model": ErrorResponse, "description": "Request validation failed"},
    500: {"model": ErrorResponse, "description": "Unexpected server error"},
}


class AppError(Exception):
    """Domain error rendered as the standard error envelope."""

    def __init__(
        self,
        code: str,
        status_code: int,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        self.headers = headers


def error_response(
    request: Request,
    code: str,
    status_code: int,
    details: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    language = negotiate_language(request.headers.get("accept-language"))
    body = {
        "error": {
            "code": code,
            "message": error_message(code, language),
            "details": details or {},
            "request_id": getattr(request.state, "request_id", None),
        }
    }
    return JSONResponse(body, status_code=status_code, headers=headers)


async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(request, exc.code, exc.status_code, exc.details, exc.headers)


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = HTTP_STATUS_CODES.get(exc.status_code, "request.failed")
    return error_response(request, code, exc.status_code, headers=exc.headers)


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Only locations and error types are returned; submitted values may contain personal data.
    fields = [{"loc": list(error["loc"]), "type": error["type"]} for error in exc.errors()]
    return error_response(request, "request.validation_failed", 422, {"fields": fields})


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", exc_info=exc)
    return error_response(request, "server.internal_error", 500)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
