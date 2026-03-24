import enum
from dataclasses import dataclass
from typing import Any


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


class ServiceUnavailable(AppError):
    def __init__(
        self,
        title: str,
        code: str,
        detail: str | None = None,
        *,
        status_code: int = 503,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            title=title,
            code=code,
            detail=detail,
            status_code=status_code,
            extra=extra,
        )


class UnprocessableEntity(AppError):
    def __init__(
        self,
        title: str,
        code: str,
        detail: str | None = None,
        *,
        status_code: int = 422,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            title=title,
            code=code,
            detail=detail,
            status_code=status_code,
            extra=extra,
        )


class DBErrorKind(enum.StrEnum):
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
    constraint_name: str | None = None
    retryable: bool = False
    cause: Exception | None = None
    detail: str | None = None


class ValidationError(ValueError):
    def __init__(self, message: str, *, cause: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause


class NameValidationError(ValidationError):
    pass
