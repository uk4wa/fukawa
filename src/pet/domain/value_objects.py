from dataclasses import dataclass
from unicodedata import normalize
from uuid import UUID

from pet.domain.exc import NameValidationError

ORG_NAME_MIN_LEN: int = 3
ORG_NAME_MAX_LEN: int = 64


@dataclass(frozen=True, slots=True)
class PublicId:
    value: UUID

    @classmethod
    def create(cls, value: UUID) -> "PublicId":
        return cls(value=value)


@dataclass(frozen=True, slots=True)
class Name:
    value: str

    @classmethod
    def create(cls, value: str) -> "Name":
        """
        DDD alias for Name()
        """
        return cls(value=value)

    def __post_init__(self) -> None:
        normalized_value = normalize("NFC", self.value.strip())

        if not normalized_value:
            raise NameValidationError("Name cannot be empty")
        if len(normalized_value) < ORG_NAME_MIN_LEN:
            raise NameValidationError("Name is too short")
        if len(normalized_value) > ORG_NAME_MAX_LEN:
            raise NameValidationError("Name is too long")

        object.__setattr__(self, "value", normalized_value)
