from typing import Any
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import (
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from pet.domain.exc import AppError, DBError
import logging

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
    async def app_error_handler(r: Request, exc: AppError):  # type:ignore
        rid = _request_id(r)
        return problem(
            title=exc.title,
            status=exc.status_code,
            detail=exc.detail,
            instance=(r.url.path),
            code=exc.code,
            request_id=rid,
        )

    @app.exception_handler(DBError)
    async def db_error_handler(request: Request, exc: DBError):  # type:ignore
        rid = _request_id(request)
        return problem(
            status=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            code=exc.kind,
            instance=str(request.url.path),
            request_id=rid,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(  # type:ignore
        r: Request, exc: StarletteHTTPException
    ):
        rid = _request_id(r)

        return problem(
            title="HTTPException",
            status=exc.status_code,
            detail=exc.detail,
            instance=(r.url.path),
            code="http_error",
            request_id=rid,
            headers=dict(exc.headers or {}),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(  # type:ignore
        request: Request, exc: RequestValidationError
    ):
        rid = _request_id(request)

        return problem(
            status=HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation Error",
            detail="Request validation failed",
            code="validation_error",
            errors=exc.errors(),
            instance=str(request.url.path),
            request_id=rid,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):  # type:ignore
        rid = _request_id(request)
        logger.exception(
            "Unhandled error", extra={"path": request.url.path, "request_id": rid}
        )
        return problem(
            status=HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="Unexpected error",
            code="internal_error",
            instance=str(request.url.path),
            request_id=rid,
        )
