"""Integration of auth dependencies with FastAPI.

Uses an isolated FastAPI app (no DB/lifespan) with a fake TokenVerifier so we
can exercise 401/403, scopes, realm roles, and client roles end-to-end via
the dependency injection wiring.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from pet.api.auth import (
    CurrentPrincipal,
    require_client_roles,
    require_realm_roles,
    require_scopes,
)
from pet.api.auth.exception_handlers import register_auth_exception_handlers
from pet.api.exceptions_handler import register_exception_handlers
from pet.app.auth.exc import InvalidToken
from pet.app.auth.verifier import TokenVerifier
from pet.domain.auth.principal import Principal

CLIENT_ID = "pet-backend"


class FakeVerifier(TokenVerifier):
    """In-memory verifier: maps a raw token string to a fixed Principal."""

    def __init__(self, principals: Mapping[str, Principal]) -> None:
        self._principals = dict(principals)

    async def verify(self, raw_token: str) -> Principal:
        principal = self._principals.get(raw_token)
        if principal is None:
            raise InvalidToken("Unknown test token")
        return principal


def _make_principal(
    *,
    subject: str = "u1",
    scopes: frozenset[str] = frozenset(),
    realm_roles: frozenset[str] = frozenset(),
    client_roles: dict[str, frozenset[str]] | None = None,
) -> Principal:
    return Principal(
        subject=subject,
        username="alice",
        email="alice@example.com",
        scopes=scopes,
        realm_roles=realm_roles,
        client_roles=MappingProxyType(client_roles or {}),
    )


def _build_app(verifier: TokenVerifier) -> FastAPI:
    app = FastAPI()
    app.state.token_verifier = verifier
    register_exception_handlers(app)
    register_auth_exception_handlers(app)

    @app.get("/me")
    async def me(principal: CurrentPrincipal) -> dict[str, str]:
        return {"sub": principal.subject}

    @app.get(
        "/scoped",
        dependencies=[Depends(require_scopes("organizations:write"))],
    )
    async def scoped() -> dict[str, bool]:
        return {"ok": True}

    @app.get(
        "/admin",
        dependencies=[Depends(require_realm_roles("admin"))],
    )
    async def admin_only() -> dict[str, bool]:
        return {"ok": True}

    @app.get(
        "/managers",
        dependencies=[Depends(require_client_roles(CLIENT_ID, "manager"))],
    )
    async def managers_only() -> dict[str, bool]:
        return {"ok": True}

    return app


@pytest.fixture
def principals() -> dict[str, Principal]:
    return {
        "tok-plain": _make_principal(subject="u-plain"),
        "tok-scoped": _make_principal(scopes=frozenset({"organizations:write"})),
        "tok-admin": _make_principal(realm_roles=frozenset({"admin", "user"})),
        "tok-manager": _make_principal(
            client_roles={CLIENT_ID: frozenset({"manager"})},
        ),
    }


@pytest.fixture
def verifier(principals: dict[str, Principal]) -> FakeVerifier:
    return FakeVerifier(principals)


@pytest.fixture
def app(verifier: FakeVerifier) -> FastAPI:
    return _build_app(verifier)


@pytest.fixture
async def client(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as c:
        yield c


class TestAuthentication:
    @pytest.mark.asyncio
    async def test_returns_401_when_no_authorization_header(self, client: AsyncClient) -> None:
        r = await client.get("/me")
        assert r.status_code == 401
        assert r.headers["www-authenticate"].lower().startswith("bearer ")
        body = r.json()
        assert body["status"] == 401

    @pytest.mark.asyncio
    async def test_returns_401_when_scheme_is_not_bearer(self, client: AsyncClient) -> None:
        r = await client.get("/me", headers={"Authorization": "Basic abc"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_401_when_token_unknown_to_verifier(self, client: AsyncClient) -> None:
        r = await client.get("/me", headers={"Authorization": "Bearer fake"})
        assert r.status_code == 401
        assert "invalid_token" in r.headers["www-authenticate"]

    @pytest.mark.asyncio
    async def test_accepts_valid_token_and_returns_principal_subject(
        self, client: AsyncClient
    ) -> None:
        r = await client.get("/me", headers={"Authorization": "Bearer tok-plain"})
        assert r.status_code == 200
        assert r.json() == {"sub": "u-plain"}


class TestAuthorization:
    @pytest.mark.asyncio
    async def test_returns_403_when_scope_missing(self, client: AsyncClient) -> None:
        r = await client.get("/scoped", headers={"Authorization": "Bearer tok-plain"})
        assert r.status_code == 403
        assert "insufficient_scope" in r.headers["www-authenticate"]

    @pytest.mark.asyncio
    async def test_passes_when_scope_present(self, client: AsyncClient) -> None:
        r = await client.get("/scoped", headers={"Authorization": "Bearer tok-scoped"})
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_403_when_realm_role_missing(self, client: AsyncClient) -> None:
        r = await client.get("/admin", headers={"Authorization": "Bearer tok-plain"})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_passes_when_realm_role_present(self, client: AsyncClient) -> None:
        r = await client.get("/admin", headers={"Authorization": "Bearer tok-admin"})
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_403_when_client_role_missing(self, client: AsyncClient) -> None:
        r = await client.get("/managers", headers={"Authorization": "Bearer tok-plain"})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_passes_when_client_role_present(self, client: AsyncClient) -> None:
        r = await client.get("/managers", headers={"Authorization": "Bearer tok-manager"})
        assert r.status_code == 200
