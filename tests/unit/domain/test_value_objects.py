from unicodedata import normalize

import pytest

from pet.domain.exc import NameValidationError
from pet.domain.value_objects import ORG_NAME_MAX_LEN, Name


def test_name_rejects_values_whose_length_exceeds_max_len() -> None:
    value = "a" * (ORG_NAME_MAX_LEN + 1)

    with pytest.raises(NameValidationError, match="Name is too long"):
        Name.create(value)


def test_name_normalizes_to_nfc() -> None:
    value = "A\u0308rger Stra\u00dfe"

    result = Name.create(value)

    assert result.value == normalize("NFC", value)
