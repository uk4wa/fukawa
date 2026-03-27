import pytest
from pydantic import ValidationError

from pet.api.organizations import CreateOrgDtoIn


def test_create_org_dto_applies_shared_name_validation() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateOrgDtoIn(name="\u00df" * 64)

    assert exc_info.value.errors()[0]["msg"] == "Value error, Name is too long"


def test_create_org_dto_schema_describes_name_contract() -> None:
    schema = CreateOrgDtoIn.model_json_schema()
    name_schema = schema["properties"]["name"]

    assert name_schema["type"] == "string"
    assert "trimmed and normalized to NFC" in name_schema["description"]
    assert "canonical form must not exceed 64 characters" in name_schema["description"]
