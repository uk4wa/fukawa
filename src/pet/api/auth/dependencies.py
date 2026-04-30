from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pet.app.auth.exc import (
    AuthenticationError,
    InsufficientPermissions,
    InvalidToken,
    MissingToken,
)
from pet.app.auth.verifier import TokenVerifier
from pet.config.logging import get_logger
from pet.domain.auth.principal import Principal

logger = get_logger(__name__)

_bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    description="Keycloak-issued OAuth 2.1 Bearer access token",
    auto_error=False,
)


def _get_verifier(request: Request) -> TokenVerifier:
    verifier: TokenVerifier | None = getattr(request.app.state, "token_verifier", None)
    if verifier is None:
        raise AuthenticationError("Token verifier is not configured")
    return verifier


async def get_current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> Principal:
    """Authenticate the request and return the verified principal.

    Raises:
        MissingToken: 401 — header absent or not Bearer.
        InvalidToken / AuthenticationError: 401 — verification failed.
    """
    if credentials is None:
        raise MissingToken()

    if (credentials.scheme or "").lower() != "bearer":
        raise MissingToken()

    raw = credentials.credentials
    if not raw:
        raise MissingToken()

    verifier = _get_verifier(request)
    try:
        principal = await verifier.verify(raw)
    except AuthenticationError:
        raise
    except Exception as exc:
        logger.error("token_verification_unexpected_error", error_class=type(exc).__name__)
        raise InvalidToken("Token verification failed") from exc

    request.state.principal = principal
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_scopes(*scopes: str) -> Callable[..., Awaitable[Principal]]:
    """Require that the access token grants ALL of `scopes`.

    Scopes are read from the `scope` (space-separated) or `scp` (list) claim.
    """
    required = frozenset(scopes)

    async def _dep(principal: CurrentPrincipal) -> Principal:
        missing = sorted(required - principal.scopes)
        if missing:
            raise InsufficientPermissions(f"Missing required scope(s): {' '.join(missing)}")
        return principal

    return _dep


def require_realm_roles(*roles: str) -> Callable[..., Awaitable[Principal]]:
    """Require ALL of the given Keycloak realm roles (`realm_access.roles`)."""
    required = frozenset(roles)

    async def _dep(principal: CurrentPrincipal) -> Principal:
        missing = sorted(required - principal.realm_roles)
        if missing:
            raise InsufficientPermissions(f"Missing required realm role(s): {' '.join(missing)}")
        return principal

    return _dep


def require_client_roles(client_id: str, *roles: str) -> Callable[..., Awaitable[Principal]]:
    """Require ALL of the given Keycloak client roles
    (`resource_access[client_id].roles`)."""
    required = frozenset(roles)

    async def _dep(principal: CurrentPrincipal) -> Principal:
        granted = principal.client_roles.get(client_id, frozenset())
        missing = sorted(required - granted)
        if missing:
            raise InsufficientPermissions(
                f"Missing required client role(s) on {client_id}: {' '.join(missing)}"
            )
        return principal

    return _dep
