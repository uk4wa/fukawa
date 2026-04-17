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


class OrganizationNameTakenError(AppError):
    def __init__(
        self,
        detail: str = "Organization name is already taken",
        extra: dict[str, Any] | None = None,
    ):
        super().__init__(
            title="Conflict", code=AppErrorCode.ORGANIZATION_NAME_TAKEN, detail=detail, extra=extra
        )


class ValidationError(AppError):
    def __init__(
        self,
        detail: str,
        extra: dict | None = None,
    ):
        super().__init__(
            title="Validation Error",
            code=AppErrorCode.VALIDATION,
            detail=detail,
            extra=extra,
        )


class Conflict(AppError):
    def __init__(
        self,
        title: str,
        code: AppErrorCode,
        detail: str | None = None,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            title=title,
            code=code,
            detail=detail,
            extra=extra,
        )


class InternalError(AppError):
    def __init__(
        self,
        title: str,
        code: AppErrorCode,
        detail: str | None = None,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            title=title,
            code=code,
            detail=detail,
            extra=extra,
        )


class ServiceUnavailable(AppError):
    def __init__(
        self,
        title: str,
        code: AppErrorCode,
        detail: str | None = None,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            title=title,
            code=code,
            detail=detail,
            extra=extra,
        )


class UnprocessableEntity(AppError):
    def __init__(
        self,
        title: str,
        code: AppErrorCode,
        detail: str | None = None,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            title=title,
            code=code,
            detail=detail,
            extra=extra,
        )
