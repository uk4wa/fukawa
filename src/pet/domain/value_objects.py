from dataclasses import dataclass
from uuid import UUID

from pet.domain.exc import NameValidationError

INVALID_CHARS: frozenset[str] = frozenset("\\#@`~*^%'\";:.,?!")


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
    def create(cls, value: str) -> "Name":
        """
        DDD alias for Name()
        """
        return cls(value=value)

    @property
    def canonical(self) -> str:
        return self.value.casefold()

    def __post_init__(self) -> None:
        normalized_value = self.value.strip()

        if not normalized_value:
            raise NameValidationError("Name cannot be empty")

        if len(normalized_value) > 320:
            raise NameValidationError("Name is too long")

        if any(ch in INVALID_CHARS for ch in normalized_value):
            raise NameValidationError("Name contains invalid characters")

        object.__setattr__(self, "value", normalized_value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Name):
            return NotImplemented
        return other.canonical == self.canonical

    def __hash__(self) -> int:
        return hash(self.canonical)
