from pet.app.errors import AppError, unprocessable_entity
from pet.domain.exc import ValidationError


def translate_domain_validation_error(e: ValidationError) -> AppError:
    return unprocessable_entity(
        detail=e.message,
        extra={
            "retryable": False,
            "cause": e.cause,
        },
    )
