import enum
from typing import Any

from pet.domain.exc import (
    AppError,
    Conflict,
    DBError,
    DBErrorKind,
    InternalError,
    ServiceUnavailable,
    UnprocessableEntity,
    ValidationError,
)

VALIDATION_ERROR_TITLE = "Validation Error"


class AppErrorCode(enum.StrEnum):
    CONFLICT = "conflict"
    INTERNAL_ERROR = "internal_error"
    ORGANIZATION_NAME_TAKEN = "organization_name_taken"
    SERVICE_UNAVAILABLE = "service_unavailable"
    VALIDATION = "validation_error"


def translate_domain_validation_error(e: ValidationError) -> AppError:
    return UnprocessableEntity(
        title=VALIDATION_ERROR_TITLE,
        code=AppErrorCode.VALIDATION,
        detail=e.message,
        extra={
            "retryable": False,
            "cause": e.cause,
        },
    )


def translate_db_error(e: DBError) -> AppError:
    extra: dict[str, Any] = {
        "retryable": e.retryable,
        "cause": e.cause,
        "constraint_name": e.constraint_name,
    }

    match e.kind:
        case DBErrorKind.UNIQUE:
            if e.constraint_name == "uq_organizations_name_canonical":
                return Conflict(
                    title="Conflict",
                    code=AppErrorCode.ORGANIZATION_NAME_TAKEN,
                    detail="Organization name is already taken",
                    extra=extra,
                )
            return Conflict(
                title="Conflict",
                code=AppErrorCode.CONFLICT,
                detail="Resource already exists",
                extra=extra,
            )
        case DBErrorKind.OPERATIONAL | DBErrorKind.TRANSIENT:
            return ServiceUnavailable(
                title="Service Unavailable",
                code=AppErrorCode.SERVICE_UNAVAILABLE,
                detail="Temporary service outage",
                status_code=e.status_code,
                extra={
                    **extra,
                    "sqlstate": e.sqlstate,
                },
            )
        case _:
            return InternalError(
                title="Internal Server Error",
                code=AppErrorCode.INTERNAL_ERROR,
                detail="Unexpected error",
                status_code=e.status_code,
                extra={
                    **extra,
                    "sqlstate": e.sqlstate,
                },
            )
