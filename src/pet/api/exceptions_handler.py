import logging
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from starlette.status import (
    HTTP_422_UNPROCESSABLE_CONTENT,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from pet.app.exc import translate_db_error
from pet.domain.exc import (
    AppError,
    DBError,
)

PROBLEM_MEDIA_TYPE = "application/problem+json"

logger = logging.getLogger("app.errors")


def _request_id(r: Request) -> str | None:
    return getattr(r.state, "request_id", None) or r.headers.get("x-request-id")


def problem(
    *,
    title: str,
    status: int,
    type_: str = "about:blank",
    detail: str | None = None,
    instance: str | None = None,
    code: str | None = None,
    errors: Any | None = None,
    request_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {"type": type_, "title": title, "status": status}
    if detail is not None:
        payload["detail"] = detail
    if instance is not None:
        payload["instance"] = instance
    if code is not None:
        payload["code"] = code
    if errors is not None:
        payload["errors"] = errors
    if request_id is not None:
        payload["request_id"] = request_id

    return JSONResponse(
        payload,
        status_code=status,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(AppError)
    async def app_error_handler(r: Request, exc: Exception) -> JSONResponse:
        app_error = cast(AppError, exc)
        rid = _request_id(r)
        return problem(
            title=app_error.title,
            status=app_error.status_code,
            detail=app_error.detail,
            instance=(r.url.path),
            code=app_error.code,
            request_id=rid,
        )

    @app.exception_handler(DBError)
    async def db_error_handler(request: Request, exc: Exception) -> JSONResponse:
        db_error = cast(DBError, exc)
        translated = translate_db_error(db_error)
        rid = _request_id(request)
        return problem(
            status=translated.status_code,
            title=translated.title,
            detail=translated.detail,
            code=translated.code,
            instance=str(request.url.path),
            request_id=rid,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(r: Request, exc: Exception) -> JSONResponse:
        http_error = cast(StarletteHTTPException, exc)
        rid = _request_id(r)

        return problem(
            title="HTTPException",
            status=http_error.status_code,
            detail=http_error.detail,
            instance=(r.url.path),
            code="http_error",
            request_id=rid,
            headers=dict(http_error.headers or {}),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
        validation_error = cast(RequestValidationError, exc)
        rid = _request_id(request)
        errors = validation_error.errors()
        detail = "Request validation failed"

        if len(errors) == 1:
            error = errors[0]
            original_error = error.get("ctx", {}).get("error")
            if hasattr(original_error, "message"):
                detail = str(original_error.message)

        return problem(
            status=HTTP_422_UNPROCESSABLE_CONTENT,
            title="Validation Error",
            detail=detail,
            code="validation_error",
            errors=errors,
            instance=str(request.url.path),
            request_id=rid,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        rid = _request_id(request)
        logger.exception("Unhandled error", extra={"path": request.url.path, "request_id": rid})
        return problem(
            status=HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="Unexpected error",
            code="internal_error",
            instance=str(request.url.path),
            request_id=rid,
        )
