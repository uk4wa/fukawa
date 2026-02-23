from dataclasses import dataclass
from typing import Any
import enum


@dataclass(slots=True)
class AppError(Exception):
    title: str
    code: str
    status_code: int = 400
    detail: str | None = None
    extra: dict[str, Any] | None = None


class Conflict(AppError):
    def __init__(
        self,
        title: str,
        code: str,
        detail: str | None = None,
        *,
        status_code: int = 409,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            title=title,
            code=code,
            detail=detail,
            status_code=status_code,
            extra=extra,
        )


class InternalError(AppError):
    def __init__(
        self,
        title: str,
        code: str,
        detail: str | None = None,
        *,
        status_code: int = 500,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            title=title,
            code=code,
            detail=detail,
            status_code=status_code,
            extra=extra,
        )


class DBErrorKind(str, enum.Enum):
    UNIQUE = "unique_violation"
    FK = "fk_violation"
    NOT_NULL = "not_null_violation"
    CHECK = "check_violation"
    OPERATIONAL = "operational"
    UNKNOWN = "unknown"
    OTHER_INTEGRITY = "other_integrity"
    TRANSIENT = "transient"


@dataclass(slots=True)
class DBError(Exception):
    kind: DBErrorKind
    title: str = "Database error"
    status_code: int = 503
    sqlstate: str | None = None
    retryable: bool = False
    cause: Exception | None = None
    detail: str | None = None


def translate_db_error(e: DBError) -> AppError:
    match e.kind:
        case DBErrorKind.UNIQUE:
            return Conflict(
                title=e.title,
                code=e.kind,
                detail=e.detail,
                extra={
                    "retryable": e.retryable,
                    "cause": e.cause,
                },
            )
        case _:
            return InternalError(
                title=e.title,
                code=e.kind,
                detail=e.detail,
                extra={
                    "retryable": e.retryable,
                    "sqlstate": e.sqlstate,
                    "cause": e.cause,
                },
            )
