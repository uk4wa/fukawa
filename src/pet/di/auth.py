import httpx

from pet.config.settings import KeycloakSettings
from pet.infra.auth.jwks import JWKSProvider
from pet.infra.auth.keycloak_verifier import KeycloakVerifier


async def build_auth_components(
    settings: KeycloakSettings,
) -> tuple[httpx.AsyncClient, JWKSProvider, KeycloakVerifier]:
    client = httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        headers={"Accept": "application/json"},
    )
    jwks = JWKSProvider(
        jwks_uri=settings.jwks_uri,
        http_client=client,
        http_timeout_seconds=settings.http_timeout_seconds,
        cache_ttl_seconds=settings.jwks_cache_ttl_seconds,
    )
    await jwks.start()

    audiences = list(dict.fromkeys([*settings.audience, settings.client_id]))

    verifier = KeycloakVerifier(
        jwks_provider=jwks,
        issuer=settings.issuer_url,
        audiences=audiences,
        allowed_algorithms=settings.allowed_algorithms,
        leeway_seconds=settings.leeway_seconds,
    )

    return client, jwks, verifier
