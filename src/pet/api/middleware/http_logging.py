from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from starlette.responses import Response

from pet.config.logging import get_logger

logger = get_logger(__name__)
SKIP_LOG_PATHS = frozenset({"/healthz", "/readyz"})


def get_duration_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def register_http_logging(app: FastAPI) -> None:
    @app.middleware("http")
    async def logging_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        structlog.contextvars.clear_contextvars()

        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id

        started_at = time.perf_counter()

        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            http_method=request.method,
            http_path=request.url.path,
        )

        try:
            response = await call_next(request)
            duration_ms = get_duration_ms(started_at)
            response.headers["X-Request-ID"] = request_id

            if request.url.path not in SKIP_LOG_PATHS:
                logger.info(
                    "http_request_finished",
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )

            return response
        finally:
            structlog.contextvars.clear_contextvars()
