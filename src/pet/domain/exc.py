class ValidationError(ValueError):
    def __init__(self, message: str, *, cause: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause


class NameValidationError(ValidationError):
    pass
