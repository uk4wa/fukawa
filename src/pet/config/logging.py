from __future__ import annotations

import logging
import logging.config
import re
from typing import Any, Final, Literal, cast
from urllib.parse import urlsplit

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

type LogFormat = Literal["json", "console"]

_VALID_LOG_LEVELS: Final[frozenset[str]] = frozenset(
    {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
)
_SKIP_ACCESS_LOG_PATHS: Final[frozenset[str]] = frozenset({"/healthz", "/readyz"})
_UVICORN_ACCESS_REQUEST_RE: Final[re.Pattern[str]] = re.compile(
    r'"[A-Z]+ (?P<path>\S+) HTTP/\d(?:\.\d)?"'
)


def _normalize_path(path: str) -> str:
    return urlsplit(path).path


def _extract_uvicorn_access_path(record: logging.LogRecord) -> str | None:
    args = record.args
    if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
        return _normalize_path(args[2])

    match = _UVICORN_ACCESS_REQUEST_RE.search(record.getMessage())
    if match is None:
        return None

    return _normalize_path(match.group("path"))


# used in dev, without --no-access-logs flag
class _UvicornAccessHealthcheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "uvicorn.access":
            return True

        path = _extract_uvicorn_access_path(record)
        return path not in _SKIP_ACCESS_LOG_PATHS


def _normalize_log_level(level: str) -> str:
    normalized = level.upper()

    if normalized not in _VALID_LOG_LEVELS:
        raise ValueError(
            f"Unsupported log level: {level!r}. "
            f"Expected one of: {', '.join(sorted(_VALID_LOG_LEVELS))}"
        )

    return normalized


def _make_static_fields_processor(fields: dict[str, Any]) -> Processor:
    def _add_static_fields(
        _logger: WrappedLogger, _method_name: str, event_dict: EventDict
    ) -> EventDict:
        for key, value in fields.items():
            event_dict.setdefault(key, value)
        return event_dict

    return _add_static_fields


_DEFAULT_SENSITIVE_KEY_FRAGMENTS: Final[frozenset[str]] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "private_key",
        "client_secret",
    }
)

_REDACTED: Final[str] = "***"


def _make_redact_processor(sensitive_key_fragments: frozenset[str]) -> Processor:
    def _is_sensitive(key: object) -> bool:
        if not isinstance(key, str):
            return False
        lowered = key.lower()
        return any(fragment in lowered for fragment in sensitive_key_fragments)

    def _redact_nested(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: (_REDACTED if _is_sensitive(k) else _redact_nested(v))
                for k, v in cast(dict[str, Any], value).items()
            }
        if isinstance(value, list):
            return [_redact_nested(item) for item in cast(list[Any], value)]
        if isinstance(value, tuple):
            return tuple(_redact_nested(item) for item in cast(tuple[Any, ...], value))
        return value

    def _redact(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
        for key in list(event_dict.keys()):
            if _is_sensitive(key):
                event_dict[key] = _REDACTED
            else:
                event_dict[key] = _redact_nested(event_dict[key])
        return event_dict

    return _redact


def configure_logging(
    *,
    level: str = "INFO",
    log_format: LogFormat = "json",
    static_fields: dict[str, Any] | None = None,
    extra_sensitive_key_fragments: frozenset[str] | None = None,
) -> None:
    normalized_level = _normalize_log_level(level)

    sensitive_key_fragments = _DEFAULT_SENSITIVE_KEY_FRAGMENTS
    if extra_sensitive_key_fragments:
        sensitive_key_fragments = sensitive_key_fragments | frozenset(
            f.lower() for f in extra_sensitive_key_fragments
        )

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _make_redact_processor(sensitive_key_fragments),
    ]

    if static_fields:
        shared_processors.insert(-1, _make_static_fields_processor(static_fields))

    formatter_processors: tuple[Processor, ...]
    if log_format == "json":
        formatter_processors = (
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        )
    else:
        formatter_processors = (
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(),
        )

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "foreign_pre_chain": shared_processors,
                    "processors": formatter_processors,
                }
            },
            "filters": {
                "skip_healthcheck_access": {
                    "()": _UvicornAccessHealthcheckFilter,
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "level": normalized_level,
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                }
            },
            "loggers": {
                "uvicorn": {
                    "handlers": ["default"],
                    "level": normalized_level,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["default"],
                    "level": normalized_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": [],
                    "level": "CRITICAL",
                    "propagate": False,
                },
                "httpx": {
                    "handlers": ["default"],
                    "level": "WARNING",
                    "propagate": False,
                },
                "sqlalchemy.engine": {
                    "handlers": ["default"],
                    "level": "WARNING",
                    "propagate": False,
                },
                "sqlalchemy.pool": {
                    "handlers": ["default"],
                    "level": "WARNING",
                    "propagate": False,
                },
            },
            "root": {
                "handlers": ["default"],
                "level": normalized_level,
            },
        }
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str, **kwargs: dict[str, str]) -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name, **kwargs)
