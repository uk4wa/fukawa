from __future__ import annotations

import logging.config
from typing import Final, Literal

import structlog
from structlog.typing import Processor

type LogFormat = Literal["json", "console"]

_VALID_LOG_LEVELS: Final[frozenset[str]] = frozenset(
    {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
)


def _normalize_log_level(level: str) -> str:
    normalized = level.upper()

    if normalized not in _VALID_LOG_LEVELS:
        raise ValueError(
            f"Unsupported log level: {level!r}. "
            f"Expected one of: {', '.join(sorted(_VALID_LOG_LEVELS))}"
        )

    return normalized


def configure_logging(*, level: str = "INFO", log_format: LogFormat = "json") -> None:
    normalized_level = _normalize_log_level(level)

    shared_processors: tuple[Processor, ...] = (
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    )
    structlog_processors: tuple[Processor, ...] = (
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        *shared_processors[1:],
    )

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
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "level": normalized_level,
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {
                "handlers": ["default"],
                "level": normalized_level,
            },
        }
    )

    structlog.configure(
        processors=[
            *structlog_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str, **kwargs: str) -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name, **kwargs)
