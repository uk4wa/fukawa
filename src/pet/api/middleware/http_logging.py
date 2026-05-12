from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import structlog
from fastapi import FastAPI, Request
from starlette.responses import Response
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from pet.api.exception_handlers import problem
from pet.config.logging import get_logger

logger = get_logger(__name__)
SKIP_LOG_PATHS = frozenset({"/healthz", "/readyz"})


def get_duration_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def _parse_request_id(raw: str | None) -> str:
    if raw:
        try:
            return str(UUID(raw))
        except ValueError:
            pass
    return uuid4().hex


def register_http_logging(app: FastAPI) -> None:
    @app.middleware("http")
    async def logging_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        structlog.contextvars.clear_contextvars()

        request_id = _parse_request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id

        started_at = time.perf_counter()

        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            http_method=request.method,
            http_path=request.url.path,
        )

        if request.url.path not in SKIP_LOG_PATHS:
            logger.info("http_request_started")

        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled_exception")
            response = problem(
                status=HTTP_500_INTERNAL_SERVER_ERROR,
                title="Internal Server Error",
                detail="Unexpected error",
                code="internal_error",
                instance=request.url.path,
                request_id=request_id,
            )

            response.headers["X-Request-ID"] = request_id

            if request.url.path not in SKIP_LOG_PATHS:
                logger.info(
                    "http_request_finished",
                    status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                    duration_ms=get_duration_ms(started_at),
                )

            return response
        else:
            response.headers["X-Request-ID"] = request_id

            if request.url.path not in SKIP_LOG_PATHS:
                logger.info(
                    "http_request_finished",
                    status_code=response.status_code,
                    duration_ms=get_duration_ms(started_at),
                )

            return response
        finally:
            structlog.contextvars.clear_contextvars()
