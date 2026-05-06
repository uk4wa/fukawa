from typing import Any, assert_never, cast

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from starlette.status import (
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_CONTENT,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from pet.app.auth.exc import AuthenticationError, AuthError, AuthorizationError
from pet.app.errors import VALIDATION_ERROR_TITLE, AppError, AppErrorCode
from pet.config.logging import get_logger

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


logger = get_logger(__name__)


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


_BEARER_REALM = "ukawa-pet"


def _www_authenticate_header(error: AuthError, status_code: int) -> str:
    parts = [f'Bearer realm="{_BEARER_REALM}"']
    parts.append(f'error="{error.error_code}"')
    if error.description:
        parts.append(f'error_description="{_escape_quoted(error.description)}"')
    return ", ".join(parts)


def _escape_quoted(value: str) -> str:
    """Escape characters that would break an HTTP quoted-string."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


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
    async def _app_error_handler(r: Request, exc: Exception) -> JSONResponse:
        app_error = cast(AppError, exc)

        status_code = get_http_status_for_error(app_error.code)
        log = logger.error if status_code >= HTTP_500_INTERNAL_SERVER_ERROR else logger.info
        log(
            "app_error_rendered",
            error_code=app_error.code,
            status_code=status_code,
        )

        return problem(
            title=app_error.title,
            status=status_code,
            detail=app_error.detail,
            instance=(r.url.path),
            code=app_error.code,
            request_id=_request_id(r),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(r: Request, exc: Exception) -> JSONResponse:
        http_error = cast(StarletteHTTPException, exc)
        if r.url.path not in ["/readyz", "/healthz"]:
            log = (
                logger.error
                if http_error.status_code >= HTTP_500_INTERNAL_SERVER_ERROR
                else logger.info
            )
            log(
                "http_exception_rendered",
                status_code=http_error.status_code,
            )

        return problem(
            title="HTTPException",
            status=http_error.status_code,
            detail=http_error.detail,
            instance=(r.url.path),
            code="http_error",
            request_id=_request_id(r),
            headers=dict(http_error.headers or {}),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
        validation_error = cast(RequestValidationError, exc)
        errors = _jsonable_validation_errors(validation_error)
        detail = "Request validation failed"

        if len(errors) == 1:
            error = errors[0]
            original_error = error.get("ctx", {}).get("error")
            if original_error is not None:
                detail = str(original_error)

        logger.info(
            "request_validation_failed",
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            errors_count=len(errors),
        )

        return problem(
            status=HTTP_422_UNPROCESSABLE_CONTENT,
            title=VALIDATION_ERROR_TITLE,
            detail=detail,
            code=AppErrorCode.VALIDATION,
            errors=errors,
            instance=str(request.url.path),
            request_id=_request_id(request),
        )

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
        )
        return problem(
            status=HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="Unexpected error",
            code="internal_error",
            instance=str(request.url.path),
            request_id=_request_id(request),
        )

    @app.exception_handler(AuthenticationError)
    async def _on_authn(r: Request, exc: Exception) -> JSONResponse:
        e = cast(AuthenticationError, exc)
        logger.info(
            "authentication_failed",
            error_code=e.error_code,
            error_class=type(e).__name__,
            error_description=e.description,
        )
        return problem(
            status=HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail=e.description,
            code=e.error_code,
            instance=r.url.path,
            request_id=_request_id(r),
            headers={"WWW-Authenticate": _www_authenticate_header(e, HTTP_401_UNAUTHORIZED)},
        )

    @app.exception_handler(AuthorizationError)
    async def _on_authz(r: Request, exc: Exception) -> JSONResponse:
        e = cast(AuthorizationError, exc)
        logger.info(
            "authorization_failed",
            error_code=e.error_code,
            error_class=type(e).__name__,
            error_description=e.description,
        )
        return problem(
            status=HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail=e.description,
            code=e.error_code,
            instance=r.url.path,
            request_id=_request_id(r),
            headers={"WWW-Authenticate": _www_authenticate_header(e, HTTP_403_FORBIDDEN)},
        )
