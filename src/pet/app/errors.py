import enum
from dataclasses import dataclass, field
from typing import Any

VALIDATION_ERROR_TITLE = "Validation Error"


class AppErrorCode(enum.StrEnum):
    CONFLICT = "conflict"
    INTERNAL_ERROR = "internal_error"
    ORGANIZATION_NAME_TAKEN = "organization_name_taken"
    SERVICE_UNAVAILABLE = "service_unavailable"
    VALIDATION = "validation_error"
    NOT_FOUND = "not_found"


@dataclass(slots=True)
class AppError(Exception):
    title: str
    code: AppErrorCode
    detail: str | None = None
    extra: dict[str, Any] = field(default_factory=lambda: {})


def conflict(
    detail: str = "Resource already exists",
    *,
    extra: dict[str, Any],
) -> AppError:
    return AppError(
        title="Conflict",
        code=AppErrorCode.CONFLICT,
        detail=detail,
        extra=extra,
    )


def organization_name_taken(
    detail: str = "Organization name is already taken",
    *,
    extra: dict[str, Any],
) -> AppError:
    return AppError(
        title="Conflict",
        code=AppErrorCode.ORGANIZATION_NAME_TAKEN,
        detail=detail,
        extra=extra,
    )


def not_found(
    detail: str = "Resource not found",
    *,
    extra: dict[str, Any] | None = None,
) -> AppError:
    return AppError(
        title="Not Found",
        code=AppErrorCode.NOT_FOUND,
        detail=detail,
        extra=extra or {},
    )


def validation_error(
    detail: str,
    *,
    extra: dict[str, Any],
) -> AppError:
    return AppError(
        title=VALIDATION_ERROR_TITLE,
        code=AppErrorCode.VALIDATION,
        detail=detail,
        extra=extra,
    )


def internal_error(
    detail: str = "Unexpected error",
    *,
    extra: dict[str, Any],
) -> AppError:
    return AppError(
        title="Internal Server Error",
        code=AppErrorCode.INTERNAL_ERROR,
        detail=detail,
        extra=extra,
    )


def service_unavailable(
    detail: str = "Temporary service outage",
    *,
    extra: dict[str, Any],
) -> AppError:
    return AppError(
        title="Service Unavailable",
        code=AppErrorCode.SERVICE_UNAVAILABLE,
        detail=detail,
        extra=extra,
    )


def unprocessable_entity(
    detail: str = "Unprocessable Entity",
    *,
    extra: dict[str, Any],
) -> AppError:
    return AppError(
        title="Unprocessable Entity",
        code=AppErrorCode.VALIDATION,
        detail=detail,
        extra=extra,
    )
