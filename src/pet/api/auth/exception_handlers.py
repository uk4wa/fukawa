from __future__ import annotations

from typing import cast

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from pet.api.exceptions_handler import problem
from pet.app.auth.exc import (
    AuthenticationError,
    AuthError,
    AuthorizationError,
)
from pet.config.logging import get_logger

logger = get_logger(__name__)

_BEARER_REALM = "pet"


def _www_authenticate_header(error: AuthError, status_code: int) -> str:
    parts = [f'Bearer realm="{_BEARER_REALM}"']
    parts.append(f'error="{error.error_code}"')
    if error.description:
        parts.append(f'error_description="{_escape_quoted(error.description)}"')
    return ", ".join(parts)


def _escape_quoted(value: str) -> str:
    """Escape characters that would break an HTTP quoted-string."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _request_id(r: Request) -> str | None:
    return getattr(r.state, "request_id", None) or r.headers.get("x-request-id")


def register_auth_exception_handlers(app: FastAPI) -> None:
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
