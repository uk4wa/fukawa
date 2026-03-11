from dataclasses import dataclass
from uuid import UUID
from pet.domain.exc import NameValidationError


@dataclass(frozen=True, slots=True)
class PublicId:
    value: UUID

    @classmethod
    def new(cls, value: UUID) -> "PublicId":
        return cls(value=value)


@dataclass(frozen=True, slots=True)
class Name:
    value: str

    @classmethod
    def new(cls, value: str) -> "Name":
        obj = cls(value=value)
        obj._validate()
        return obj

    def _validate(self) -> str:
        if len(self.value) > 320:
            raise NameValidationError("Name is too long")
        return self.value.lower()
