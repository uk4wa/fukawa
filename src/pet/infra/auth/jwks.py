from __future__ import annotations

import asyncio
import time
from typing import Final

import httpx
import jwt
from jwt import PyJWK

from pet.app.auth.exc import InvalidToken, TokenVerificationUnavailable
from pet.config.logging import get_logger

logger = get_logger(__name__)

_MIN_REFRESH_INTERVAL_SECONDS: Final = 5.0
"""Hard floor between forced refreshes triggered by an unknown 'kid', to
prevent a malicious or buggy client from weaponising key rotation handling
into an unbounded outbound JWKS fetch loop."""


def _rebase_discovered_url(url: str, *, public_issuer: str, internal_issuer: str) -> str:
    public_prefix = public_issuer.rstrip("/")
    internal_prefix = internal_issuer.rstrip("/")
    if url.startswith(public_prefix):
        return f"{internal_prefix}{url.removeprefix(public_prefix)}"
    return url


class JwksProvider:
    """Async JWKS cache with OIDC discovery, TTL, and on-rotation refresh.

    Lifecycle:
      * `start()` performs the initial discovery + JWKS fetch (fail-fast).
      * `get_signing_key(kid)` returns the public key. On unknown kid we force
        a refresh (rate-limited) to handle key rotation.
      * `aclose()` shuts the underlying HTTP client.
    """

    def __init__(
        self,
        *,
        issuer: str,
        internal_issuer: str | None = None,
        discovery_url: str,
        cache_ttl_seconds: int,
        http_timeout_seconds: float,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._issuer = issuer.rstrip("/")
        self._internal_issuer = (internal_issuer or issuer).rstrip("/")
        self._discovery_url = discovery_url
        self._cache_ttl = cache_ttl_seconds
        self._http_timeout = http_timeout_seconds
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=http_timeout_seconds)

        self._jwks_uri: str | None = None
        self._keys_by_kid: dict[str, PyJWK] = {}
        self._fetched_at: float = 0.0
        self._last_forced_refresh: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def issuer(self) -> str:
        return self._issuer

    async def start(self) -> None:
        """Perform initial OIDC discovery + JWKS load. Fails fast on errors."""
        async with self._lock:
            await self._discover_locked()
            await self._refresh_locked()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_signing_key(self, kid: str | None) -> PyJWK:
        if not kid:
            raise InvalidToken("Token header is missing 'kid'")

        key = self._keys_by_kid.get(kid)
        if key is not None and not self._is_stale():
            return key

        async with self._lock:
            key = self._keys_by_kid.get(kid)
            if key is not None and not self._is_stale():
                return key

            if key is None:
                now = time.monotonic()
                if now - self._last_forced_refresh < _MIN_REFRESH_INTERVAL_SECONDS:
                    raise InvalidToken("Unknown signing key")
                self._last_forced_refresh = now

            await self._refresh_locked()
            key = self._keys_by_kid.get(kid)
            if key is None:
                raise InvalidToken("Unknown signing key")
            return key

    def _is_stale(self) -> bool:
        if self._cache_ttl <= 0:
            return True
        return (time.monotonic() - self._fetched_at) >= self._cache_ttl

    async def _discover_locked(self) -> None:
        try:
            response = await self._client.get(self._discovery_url)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error(
                "oidc_discovery_failed",
                issuer=self._issuer,
                error_class=type(exc).__name__,
            )
            raise TokenVerificationUnavailable("OIDC discovery failed") from exc

        if not isinstance(payload, dict):
            raise TokenVerificationUnavailable("OIDC discovery payload has unexpected shape")

        discovered_issuer = str(payload.get("issuer", "")).rstrip("/")
        if discovered_issuer != self._issuer:
            logger.error(
                "oidc_discovery_issuer_mismatch",
                expected_issuer=self._issuer,
                discovered_issuer=discovered_issuer,
            )
            raise TokenVerificationUnavailable("OIDC discovery issuer mismatch")

        jwks_uri = payload.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise TokenVerificationUnavailable("OIDC discovery missing jwks_uri")

        self._jwks_uri = _rebase_discovered_url(
            jwks_uri,
            public_issuer=self._issuer,
            internal_issuer=self._internal_issuer,
        )

    async def _refresh_locked(self) -> None:
        if self._jwks_uri is None:
            await self._discover_locked()

        if self._jwks_uri is None:
            raise ValueError("JWKS uri not initialized")

        try:
            response = await self._client.get(self._jwks_uri)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error(
                "jwks_fetch_failed",
                jwks_uri=self._jwks_uri,
                error_class=type(exc).__name__,
            )
            raise TokenVerificationUnavailable("JWKS fetch failed") from exc

        if not isinstance(payload, dict):
            raise TokenVerificationUnavailable("JWKS payload has unexpected shape")

        try:
            jwk_set = jwt.PyJWKSet.from_dict(payload)
        except (jwt.PyJWTError, KeyError, TypeError) as exc:
            logger.error("jwks_parse_failed", error_class=type(exc).__name__)
            raise TokenVerificationUnavailable("JWKS parse failed") from exc

        keys: dict[str, PyJWK] = {}
        for key in jwk_set.keys:
            kid = getattr(key, "key_id", None)
            if kid:
                keys[kid] = key

        if not keys:
            raise TokenVerificationUnavailable("JWKS contains no usable keys")

        self._keys_by_kid = keys
        self._fetched_at = time.monotonic()
        logger.info("jwks_refreshed", key_count=len(keys))
