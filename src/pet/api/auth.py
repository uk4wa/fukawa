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
from pet.app.auth.verifier import TokenVerifierAbstract
from pet.di.db import TransactionExecutor, get_executor
from pet.domain.auth import Principal

_bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    description="Keycloak-issued OAuth 2.1 Bearer access token",
    auto_error=False,
)


def _get_verifier(request: Request) -> TokenVerifierAbstract:
    return request.app.state.token_verifier


async def get_current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    executor: Annotated[TransactionExecutor, Depends(get_executor)],
) -> Principal:
    if credentials is None:
        raise MissingToken()

    verifier = _get_verifier(request)
    try:
        principal = await verifier.verify(credentials.credentials)
    except AuthenticationError:
        raise
    except Exception as exc:
        raise InvalidToken("Token verification failed") from exc

    request.state.principal = principal
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def required_scopes(*scopes: str) -> Callable[..., Awaitable[Principal]]:
    required = frozenset(scopes)

    async def _dep(principal: CurrentPrincipal) -> Principal:
        missing = sorted(required - principal.scopes)
        if missing:
            raise InsufficientPermissions(f"Missing required scope(s) {' '.join(missing)}")
        return principal

    return _dep


def required_realm_roles(*roles: str) -> Callable[..., Awaitable[Principal]]:
    required = frozenset(roles)

    async def _dep(principal: CurrentPrincipal) -> Principal:
        missing = sorted(required - principal.realm_roles)
        if missing:
            raise InsufficientPermissions(f"Missing required realm role(s) {' '.join(missing)}")
        return principal

    return _dep


def required_client_roles(client_id: str, *roles: str) -> Callable[..., Awaitable[Principal]]:
    required = frozenset(roles)

    async def _dep(principal: CurrentPrincipal) -> Principal:
        granted = principal.client_roles.get(client_id, frozenset())
        missing = sorted(required - granted)
        if missing:
            raise InsufficientPermissions(f"Missing required client role(s) {' '.join(missing)}")
        return principal

    return _dep
