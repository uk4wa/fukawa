"""Tests for JwksProvider — discovery, JWKS load, caching, rotation, errors."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from pet.app.auth.exc import InvalidToken, TokenVerificationUnavailable
from pet.infra.auth.jwks import JwksProvider

from ._keys import RsaTestKey, make_rsa_key

ISSUER = "https://auth.example.com/realms/pet"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"
JWKS_URI = f"{ISSUER}/protocol/openid-connect/certs"


def _discovery_payload(issuer: str = ISSUER, jwks_uri: str = JWKS_URI) -> dict[str, Any]:
    return {"issuer": issuer, "jwks_uri": jwks_uri}


def _jwks_payload(*keys: RsaTestKey) -> dict[str, Any]:
    return {"keys": [k.public_jwk for k in keys]}


def _mock_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


@pytest.fixture
async def http_client_factory() -> AsyncIterator[
    Callable[[Callable[[httpx.Request], httpx.Response]], httpx.AsyncClient]
]:
    clients: list[httpx.AsyncClient] = []

    def _make(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
        client = httpx.AsyncClient(transport=_mock_transport(handler), timeout=2.0)
        clients.append(client)
        return client

    yield _make

    for c in clients:
        await c.aclose()


def _provider(client: httpx.AsyncClient, *, ttl: int = 300) -> JwksProvider:
    return JwksProvider(
        issuer=ISSUER,
        internal_issuer=ISSUER,
        discovery_url=DISCOVERY_URL,
        cache_ttl_seconds=ttl,
        http_timeout_seconds=2.0,
        http_client=client,
    )


@pytest.mark.asyncio
async def test_start_loads_keys(
    http_client_factory: Callable[..., httpx.AsyncClient],
) -> None:
    key = make_rsa_key(kid="k1")

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == DISCOVERY_URL:
            return httpx.Response(200, json=_discovery_payload())
        if str(request.url) == JWKS_URI:
            return httpx.Response(200, json=_jwks_payload(key))
        return httpx.Response(404)

    p = _provider(http_client_factory(handler))
    await p.start()
    found = await p.get_signing_key("k1")
    assert found.key_id == "k1"


@pytest.mark.asyncio
async def test_start_fails_when_discovery_issuer_mismatches(
    http_client_factory: Callable[..., httpx.AsyncClient],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == DISCOVERY_URL:
            return httpx.Response(200, json=_discovery_payload(issuer="https://elsewhere/x"))
        return httpx.Response(404)

    p = _provider(http_client_factory(handler))
    with pytest.raises(TokenVerificationUnavailable):
        await p.start()


@pytest.mark.asyncio
async def test_start_fails_on_jwks_http_error(
    http_client_factory: Callable[..., httpx.AsyncClient],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == DISCOVERY_URL:
            return httpx.Response(200, json=_discovery_payload())
        return httpx.Response(503)

    p = _provider(http_client_factory(handler))
    with pytest.raises(TokenVerificationUnavailable):
        await p.start()


@pytest.mark.asyncio
async def test_unknown_kid_triggers_refresh_and_picks_up_rotation(
    http_client_factory: Callable[..., httpx.AsyncClient],
) -> None:
    """JWKS rotation: kid 'k2' appears only after the first refresh."""
    k1 = make_rsa_key(kid="k1")
    k2 = make_rsa_key(kid="k2")

    state = {"jwks_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == DISCOVERY_URL:
            return httpx.Response(200, json=_discovery_payload())
        if str(request.url) == JWKS_URI:
            state["jwks_calls"] += 1
            if state["jwks_calls"] == 1:
                return httpx.Response(200, json=_jwks_payload(k1))
            return httpx.Response(200, json=_jwks_payload(k1, k2))
        return httpx.Response(404)

    p = _provider(http_client_factory(handler))
    await p.start()

    # First lookup of unknown kid forces refresh -> finds k2.
    found = await p.get_signing_key("k2")
    assert found.key_id == "k2"
    assert state["jwks_calls"] == 2


@pytest.mark.asyncio
async def test_repeated_unknown_kid_is_rate_limited(
    http_client_factory: Callable[..., httpx.AsyncClient],
) -> None:
    k1 = make_rsa_key(kid="k1")
    state = {"jwks_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == DISCOVERY_URL:
            return httpx.Response(200, json=_discovery_payload())
        if str(request.url) == JWKS_URI:
            state["jwks_calls"] += 1
            return httpx.Response(200, json=_jwks_payload(k1))
        return httpx.Response(404)

    p = _provider(http_client_factory(handler), ttl=300)
    await p.start()
    assert state["jwks_calls"] == 1

    # First unknown kid forces refresh once, beyond that we should NOT
    # re-fetch within the rate-limit window.
    for _ in range(5):
        with pytest.raises(InvalidToken):
            await p.get_signing_key("rogue")

    # Initial start (1) + one forced refresh (1) = 2.
    assert state["jwks_calls"] == 2


@pytest.mark.asyncio
async def test_rejects_blank_kid(
    http_client_factory: Callable[..., httpx.AsyncClient],
) -> None:
    k1 = make_rsa_key(kid="k1")

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == DISCOVERY_URL:
            return httpx.Response(200, json=_discovery_payload())
        return httpx.Response(200, json=_jwks_payload(k1))

    p = _provider(http_client_factory(handler))
    await p.start()
    with pytest.raises(InvalidToken):
        await p.get_signing_key(None)


@pytest.mark.asyncio
async def test_jwks_with_no_usable_keys_raises(
    http_client_factory: Callable[..., httpx.AsyncClient],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == DISCOVERY_URL:
            return httpx.Response(200, json=_discovery_payload())
        return httpx.Response(200, json={"keys": []})

    p = _provider(http_client_factory(handler))
    with pytest.raises(TokenVerificationUnavailable):
        await p.start()


@pytest.mark.asyncio
async def test_aclose_closes_owned_client() -> None:
    """When the provider owns its HTTP client it should close it on aclose."""
    p = JwksProvider(
        issuer=ISSUER,
        internal_issuer=ISSUER,
        discovery_url=DISCOVERY_URL,
        cache_ttl_seconds=10,
        http_timeout_seconds=1.0,
    )
    # Don't start (would require a real network); just verify aclose is safe.
    await p.aclose()


@pytest.mark.asyncio
async def test_rebases_jwks_uri_to_internal_issuer(
    http_client_factory: Callable[..., httpx.AsyncClient],
) -> None:
    key = make_rsa_key(kid="k1")
    internal_issuer = "http://keycloak:8080/realms/pet"
    internal_discovery_url = f"{internal_issuer}/.well-known/openid-configuration"
    internal_jwks_uri = f"{internal_issuer}/protocol/openid-connect/certs"

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == internal_discovery_url:
            return httpx.Response(200, json=_discovery_payload())
        if str(request.url) == internal_jwks_uri:
            return httpx.Response(200, json=_jwks_payload(key))
        return httpx.Response(404)

    provider = JwksProvider(
        issuer=ISSUER,
        internal_issuer=internal_issuer,
        discovery_url=internal_discovery_url,
        cache_ttl_seconds=300,
        http_timeout_seconds=2.0,
        http_client=http_client_factory(handler),
    )

    await provider.start()
    found = await provider.get_signing_key("k1")
    assert found.key_id == "k1"
