import pytest

from pet.domain.exc import NameValidationError
from pet.domain.value_objects import ORG_NAME_MAX_LEN, Name


def test_name_rejects_values_whose_casefold_exceeds_max_len() -> None:
    value = "\u00df" * ORG_NAME_MAX_LEN

    with pytest.raises(NameValidationError, match="Name is too long"):
        Name.create(value)
