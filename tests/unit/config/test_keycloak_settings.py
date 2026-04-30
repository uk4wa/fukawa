from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from pet.config.settings import DatabaseSettings, KeycloakSettings, Settings


def _db() -> DatabaseSettings:
    return DatabaseSettings(
        driver="postgresql+asyncpg",
        host="localhost",
        name="pet",
        user="u",
        port=5432,
        password=SecretStr("p"),
    )


def _kc(**over: object) -> KeycloakSettings:
    base: dict[str, object] = {
        "issuer_url": "https://auth.example.com/realms/pet",
        "client_id": "pet-backend",
        "audience": ["pet-backend"],
        "allowed_algorithms": ["RS256"],
    }
    base.update(over)
    return KeycloakSettings(**base)  # type: ignore[arg-type]


def test_issuer_normalises_trailing_slash() -> None:
    kc = _kc(issuer_url="https://auth.example.com/realms/pet/")
    assert kc.issuer == "https://auth.example.com/realms/pet"


def test_discovery_url_uses_well_known() -> None:
    kc = _kc()
    assert (
        kc.discovery_url == "https://auth.example.com/realms/pet/.well-known/openid-configuration"
    )


def test_discovery_url_uses_internal_issuer_when_configured() -> None:
    kc = _kc(internal_issuer_url="http://keycloak:8080/realms/pet")
    assert kc.internal_issuer == "http://keycloak:8080/realms/pet"
    assert kc.discovery_url == "http://keycloak:8080/realms/pet/.well-known/openid-configuration"


def test_rejects_alg_none() -> None:
    with pytest.raises(ValidationError):
        _kc(allowed_algorithms=["none"])


def test_rejects_empty_alg_list() -> None:
    with pytest.raises(ValidationError):
        _kc(allowed_algorithms=[])


# def test_settings_requires_keycloak() -> None:
#     with pytest.raises(ValidationError):
#         Settings(_env_file=None, db=_db())  # type: ignore[call-arg]


def test_settings_accepts_keycloak() -> None:
    s = Settings(_env_file=None, db=_db(), keycloak=_kc())  # type: ignore[call-arg]
    assert s.keycloak.client_id == "pet-backend"
