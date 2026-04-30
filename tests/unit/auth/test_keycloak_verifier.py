"""Unit tests for KeycloakTokenVerifier.

These tests stand up a fake JwksProvider that returns in-memory PyJWK keys
generated per test, then sign synthetic tokens with our private key. No
network and no Keycloak dependency.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import jwt
import pytest

from pet.app.auth.exc import InvalidToken, TokenVerificationUnavailable
from pet.infra.auth.keycloak_verifier import KeycloakTokenVerifier

from ._keys import RsaTestKey, make_rsa_key

ISSUER = "https://auth.example.com/realms/pet"
CLIENT_ID = "pet-backend"


class _StubJwks:
    """Test double for JwksProvider. Allows simulating rotation and outages."""

    def __init__(self, keys: dict[str, RsaTestKey]) -> None:
        self.keys = keys
        self.calls = 0
        self.unavailable = False

    async def get_signing_key(self, kid: str | None) -> jwt.PyJWK:
        self.calls += 1
        if self.unavailable:
            raise TokenVerificationUnavailable("JWKS down")
        if not kid or kid not in self.keys:
            raise InvalidToken("Unknown signing key")
        return jwt.PyJWK.from_dict(self.keys[kid].public_jwk)


def _build_verifier(
    jwks: _StubJwks,
    *,
    audiences: list[str] | None = None,
    algorithms: list[str] | None = None,
    leeway: int = 5,
) -> KeycloakTokenVerifier:
    return KeycloakTokenVerifier(
        jwks=jwks,  # type: ignore[arg-type]
        issuer=ISSUER,
        audiences=audiences if audiences is not None else [CLIENT_ID],
        allowed_algorithms=algorithms or ["RS256"],
        leeway_seconds=leeway,
    )


def _now() -> int:
    return int(time.time())


def _claims(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "iss": ISSUER,
        "sub": "user-123",
        "aud": CLIENT_ID,
        "azp": CLIENT_ID,
        "iat": _now() - 1,
        "nbf": _now() - 1,
        "exp": _now() + 60,
        "preferred_username": "alice",
        "email": "alice@example.com",
        "scope": "organizations:read organizations:write",
        "realm_access": {"roles": ["user", "admin"]},
        "resource_access": {CLIENT_ID: {"roles": ["manager"]}},
    }
    base.update(overrides)
    return base


@pytest.fixture
def key() -> RsaTestKey:
    return make_rsa_key(kid="key-1")


@pytest.fixture
def jwks(key: RsaTestKey) -> _StubJwks:
    return _StubJwks({key.kid: key})


@pytest.fixture
async def verifier(jwks: _StubJwks) -> AsyncIterator[KeycloakTokenVerifier]:
    yield _build_verifier(jwks)


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_verifies_valid_token_and_extracts_principal(
        self, key: RsaTestKey, verifier: KeycloakTokenVerifier
    ) -> None:
        token = key.sign(_claims())

        principal = await verifier.verify(token)

        assert principal.subject == "user-123"
        assert principal.username == "alice"
        assert principal.email == "alice@example.com"
        assert principal.has_realm_role("admin")
        assert principal.has_client_role(CLIENT_ID, "manager")
        assert principal.has_scope("organizations:read")
        assert principal.has_scope("organizations:write")

    @pytest.mark.asyncio
    async def test_supports_scp_list_claim(
        self, key: RsaTestKey, verifier: KeycloakTokenVerifier
    ) -> None:
        token = key.sign(_claims(scope=None, scp=["a", "b"]))
        principal = await verifier.verify(token)
        assert principal.scopes == frozenset({"a", "b"})

    @pytest.mark.asyncio
    async def test_accepts_audience_via_azp_when_aud_does_not_match(
        self, key: RsaTestKey, jwks: _StubJwks
    ) -> None:
        verifier = _build_verifier(jwks, audiences=[CLIENT_ID])
        token = key.sign(_claims(aud="other-service", azp=CLIENT_ID))
        principal = await verifier.verify(token)
        assert principal.subject == "user-123"


class TestRejection:
    @pytest.mark.asyncio
    async def test_rejects_bad_signature(self, key: RsaTestKey, jwks: _StubJwks) -> None:
        # Sign with a different key than the one served by JWKS.
        attacker = make_rsa_key(kid=key.kid)
        verifier = _build_verifier(jwks)
        token = attacker.sign(_claims())

        with pytest.raises(InvalidToken):
            await verifier.verify(token)

    @pytest.mark.asyncio
    async def test_rejects_wrong_issuer(
        self, key: RsaTestKey, verifier: KeycloakTokenVerifier
    ) -> None:
        token = key.sign(_claims(iss="https://evil.example.com/realms/pet"))
        with pytest.raises(InvalidToken):
            await verifier.verify(token)

    @pytest.mark.asyncio
    async def test_rejects_wrong_audience(
        self, key: RsaTestKey, verifier: KeycloakTokenVerifier
    ) -> None:
        token = key.sign(_claims(aud="not-our-client", azp="not-our-client"))
        with pytest.raises(InvalidToken):
            await verifier.verify(token)

    @pytest.mark.asyncio
    async def test_rejects_expired_token(
        self, key: RsaTestKey, verifier: KeycloakTokenVerifier
    ) -> None:
        token = key.sign(_claims(exp=_now() - 600, iat=_now() - 700))
        with pytest.raises(InvalidToken):
            await verifier.verify(token)

    @pytest.mark.asyncio
    async def test_rejects_not_yet_valid_token(self, key: RsaTestKey, jwks: _StubJwks) -> None:
        verifier = _build_verifier(jwks, leeway=0)
        token = key.sign(_claims(nbf=_now() + 600, iat=_now() + 600, exp=_now() + 1200))
        with pytest.raises(InvalidToken):
            await verifier.verify(token)

    @pytest.mark.asyncio
    async def test_rejects_disallowed_algorithm_in_header(self, jwks: _StubJwks) -> None:
        # Hand-crafted token with alg=HS256, which is not in the allow-list.
        verifier = _build_verifier(jwks, algorithms=["RS256"])
        bad = jwt.encode(_claims(), key="k" * 32, algorithm="HS256", headers={"kid": "key-1"})
        with pytest.raises(InvalidToken):
            await verifier.verify(bad)

    @pytest.mark.asyncio
    async def test_rejects_unknown_kid(
        self, key: RsaTestKey, verifier: KeycloakTokenVerifier
    ) -> None:
        rogue = make_rsa_key(kid="not-in-jwks")
        token = rogue.sign(_claims())
        with pytest.raises(InvalidToken):
            await verifier.verify(token)

    @pytest.mark.asyncio
    async def test_rejects_token_missing_kid(
        self, key: RsaTestKey, verifier: KeycloakTokenVerifier
    ) -> None:
        token = jwt.encode(_claims(), key=key.private_pem, algorithm="RS256")  # no kid
        with pytest.raises(InvalidToken):
            await verifier.verify(token)

    @pytest.mark.asyncio
    async def test_rejects_malformed_token(self, verifier: KeycloakTokenVerifier) -> None:
        with pytest.raises(InvalidToken):
            await verifier.verify("not.a.jwt")

    @pytest.mark.asyncio
    async def test_jwks_outage_propagates_as_unavailable(
        self, key: RsaTestKey, jwks: _StubJwks, verifier: KeycloakTokenVerifier
    ) -> None:
        jwks.unavailable = True
        token = key.sign(_claims())
        with pytest.raises(TokenVerificationUnavailable):
            await verifier.verify(token)


class TestConstructorGuards:
    def test_rejects_none_algorithm(self, jwks: _StubJwks) -> None:
        with pytest.raises(ValueError):
            KeycloakTokenVerifier(
                jwks=jwks,  # type: ignore[arg-type]
                issuer=ISSUER,
                audiences=[CLIENT_ID],
                allowed_algorithms=["none"],
                leeway_seconds=0,
            )

    def test_rejects_empty_algorithm_list(self, jwks: _StubJwks) -> None:
        with pytest.raises(ValueError):
            KeycloakTokenVerifier(
                jwks=jwks,  # type: ignore[arg-type]
                issuer=ISSUER,
                audiences=[CLIENT_ID],
                allowed_algorithms=[],
                leeway_seconds=0,
            )
