import logging
from typing import Any, assert_never, cast

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from starlette.status import (
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_CONTENT,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from pet.app.errors import VALIDATION_ERROR_TITLE, AppError, AppErrorCode

PROBLEM_MEDIA_TYPE = "application/problem+json"


def get_http_status_for_error(code: AppErrorCode) -> int:
    match code:
        case AppErrorCode.CONFLICT | AppErrorCode.ORGANIZATION_NAME_TAKEN:
            return HTTP_409_CONFLICT
        case AppErrorCode.VALIDATION:
            return HTTP_422_UNPROCESSABLE_CONTENT
        case AppErrorCode.SERVICE_UNAVAILABLE:
            return HTTP_503_SERVICE_UNAVAILABLE
        case AppErrorCode.INTERNAL_ERROR:
            return HTTP_500_INTERNAL_SERVER_ERROR
        case _:
            assert_never(code)


logger = logging.getLogger("app.errors")


def _request_id(r: Request) -> str | None:
    return getattr(r.state, "request_id", None) or r.headers.get("x-request-id")


def _jsonable_validation_errors(validation_error: RequestValidationError) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        jsonable_encoder(
            validation_error.errors(),
            custom_encoder={Exception: str},
        ),
    )


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

        status_code = get_http_status_for_error(app_error.code)

        return problem(
            title=app_error.title,
            status=status_code,
            detail=app_error.detail,
            instance=(r.url.path),
            code=app_error.code,
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
        errors = _jsonable_validation_errors(validation_error)
        detail = "Request validation failed"

        if len(errors) == 1:
            error = errors[0]
            original_error = error.get("ctx", {}).get("error")
            if original_error is not None:
                detail = str(original_error)

        return problem(
            status=HTTP_422_UNPROCESSABLE_CONTENT,
            title=VALIDATION_ERROR_TITLE,
            detail=detail,
            code=AppErrorCode.VALIDATION,
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
