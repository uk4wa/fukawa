from dataclasses import dataclass
from unicodedata import normalize
from uuid import UUID

from pet.domain.exc import NameValidationError

ORG_NAME_MIN_LEN: int = 3
ORG_NAME_MAX_LEN: int = 64
ORG_NAME_DESCRIPTION = (
    "Organization name. The value is trimmed and normalized to NFC before validation. "
    f"The normalized value must be between {ORG_NAME_MIN_LEN} and {ORG_NAME_MAX_LEN} "
    "characters long, and its NFC(casefold(name)) canonical form must not exceed "
    f"{ORG_NAME_MAX_LEN} characters."
)


def normalize_org_name(value: str) -> str:
    return normalize("NFC", value.strip())


def canonicalize_org_name(value: str) -> str:
    return normalize("NFC", value.casefold())


def validate_org_name(value: str) -> str:
    normalized_value = normalize_org_name(value)
    canonical_value = canonicalize_org_name(normalized_value)

    if not normalized_value:
        raise NameValidationError("Name cannot be empty")
    if len(normalized_value) < ORG_NAME_MIN_LEN:
        raise NameValidationError("Name is too short")
    if len(normalized_value) > ORG_NAME_MAX_LEN:
        raise NameValidationError("Name is too long")
    if len(canonical_value) > ORG_NAME_MAX_LEN:
        raise NameValidationError("Name is too long")

    return normalized_value


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
        object.__setattr__(self, "value", validate_org_name(self.value))
