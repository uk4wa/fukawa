from pet.app.errors import (
    VALIDATION_ERROR_TITLE,
    AppError,
    AppErrorCode,
    UnprocessableEntity,
)
from pet.domain.exc import ValidationError


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
