from __future__ import annotations

import httpx

from pet.app.auth.verifier import TokenVerifier
from pet.config.settings import KeycloakSettings
from pet.infra.auth.jwks import JwksProvider
from pet.infra.auth.keycloak_verifier import KeycloakTokenVerifier


async def build_auth_components(
    settings: KeycloakSettings,
) -> tuple[httpx.AsyncClient, JwksProvider, TokenVerifier]:
    """Construct and start the auth components used by the API layer.

    Caller owns the lifecycle: invoke `aclose()` on the returned http client
    (and call `aclose()` on the JWKS provider) during shutdown.
    """
    http_client = httpx.AsyncClient(timeout=settings.http_timeout_seconds)

    jwks = JwksProvider(
        issuer=settings.issuer,
        internal_issuer=settings.internal_issuer,
        discovery_url=settings.discovery_url,
        cache_ttl_seconds=settings.jwks_cache_ttl_seconds,
        http_timeout_seconds=settings.http_timeout_seconds,
        http_client=http_client,
    )
    await jwks.start()

    audiences = list(dict.fromkeys([*settings.audience, settings.client_id]))
    verifier = KeycloakTokenVerifier(
        jwks=jwks,
        issuer=settings.issuer,
        audiences=audiences,
        allowed_algorithms=settings.allowed_algorithms,
        leeway_seconds=settings.leeway_seconds,
    )

    return http_client, jwks, verifier
