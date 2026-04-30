import enum
from dataclasses import dataclass
from typing import Any

VALIDATION_ERROR_TITLE = "Validation Error"


class AppErrorCode(enum.StrEnum):
    CONFLICT = "conflict"
    INTERNAL_ERROR = "internal_error"
    ORGANIZATION_NAME_TAKEN = "organization_name_taken"
    SERVICE_UNAVAILABLE = "service_unavailable"
    VALIDATION = "validation_error"


@dataclass(slots=True)
class AppError(Exception):
    title: str
    code: AppErrorCode
    detail: str | None = None
    extra: dict[str, Any] | None = None


class Conflict(AppError):
    pass


class InternalError(AppError):
    pass


class ServiceUnavailable(AppError):
    pass


class UnprocessableEntity(AppError):
    pass
