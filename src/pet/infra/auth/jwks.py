import asyncio
import time
from typing import Any, cast

import httpx
from jwt import PyJWK, PyJWKSet, PyJWTError

from pet.config.logging import get_logger
from pet.infra.auth.exc import JwksProviderUnavailable, SigningKeyNotFound

_DEFAULT_HTTP_TIMEOUT_SECONDS = 5.0
_DEFAULT_MIN_FORCED_REFRESH_INTERVAL_SECONDS = 5.0
_DEFAULT_CACHE_TTL_SECONDS = 300.0
_DEFAULT_MAX_STALE_SECONDS = 300.0
_DEFAULT_ALLOWED_KEY_TYPES = frozenset({"RSA"})
_DEFAULT_ALLOWED_PUBLIC_KEY_USES = frozenset({"sig"})
_DEFAULT_ALLOWED_ALGORITHMS = frozenset({"RS256"})

logger = get_logger(__name__)


class JWKSProvider:
    def __init__(
        self,
        jwks_uri: str,
        http_client: httpx.AsyncClient,
        http_timeout_seconds: float = _DEFAULT_HTTP_TIMEOUT_SECONDS,
        allowed_key_types: frozenset[str] = _DEFAULT_ALLOWED_KEY_TYPES,
        allowed_public_key_uses: frozenset[str] = _DEFAULT_ALLOWED_PUBLIC_KEY_USES,
        allowed_algorithms: frozenset[str] = _DEFAULT_ALLOWED_ALGORITHMS,
        cache_ttl_seconds: float = _DEFAULT_CACHE_TTL_SECONDS,
        max_stale_seconds: float = _DEFAULT_MAX_STALE_SECONDS,
        min_forced_refresh_interval_seconds: float = _DEFAULT_MIN_FORCED_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        if not jwks_uri:
            raise ValueError("jwks_uri must not be empty")

        if cache_ttl_seconds <= 0:
            raise ValueError("cache_ttl_seconds must be positive")

        if max_stale_seconds < 0:
            raise ValueError("max_stale_seconds must be non-negative")

        if min_forced_refresh_interval_seconds <= 0:
            raise ValueError("min_forced_refresh_interval_seconds must be positive")

        if http_timeout_seconds <= 0:
            raise ValueError("http_timeout_seconds must be positive")

        self._jwks_uri: str = jwks_uri
        self._keys_by_kid: dict[str, PyJWK] = {}

        self._http_client: httpx.AsyncClient = http_client
        self._http_timeout_seconds = http_timeout_seconds

        self._cache_ttl_seconds: float = cache_ttl_seconds
        self._max_stale_seconds: float = max_stale_seconds

        self._allowed_key_types = allowed_key_types
        self._allowed_public_key_uses = allowed_public_key_uses
        self._allowed_algorithms = allowed_algorithms

        self._min_forced_refresh_interval_seconds: float = min_forced_refresh_interval_seconds
        self._last_forced_refresh_at_monotonic: float = 0.0
        self._fetched_at_monotonic: float | None = None

        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Perform initial OIDC JWKS fetch.

        Use this in FastAPI lifespan startup.

        This is intentionally fail-fast:
        if Provider JWKS is broken at startup, the app should not
        silently start with a broken auth subsystem.
        """
        async with self._lock:
            await self._refresh()

    async def get_signing_key(self, kid: str) -> PyJWK:
        """Return signing key for kid.

        Behavior:
          - if key exists and cache is fresh: return immediately;
          - if cache is stale: refresh JWKS;
          - if kid is unknown while cache is fresh: force refresh, but rate-limited;
          - if refresh fails and stale key exists: optionally return stale key;
          - if key is still unknown after refresh: raise SigningKeyNotFound.
        """

        key = self._keys_by_kid.get(kid)
        if key is not None and not self._is_stale():
            return key

        async with self._lock:
            key = self._keys_by_kid.get(kid)
            is_stale = self._is_stale()

            if key is not None and not is_stale:
                return key

            if key is None and not is_stale:
                self._enforce_forced_refresh_rate_limit(kid)

            try:
                await self._refresh()
            except JwksProviderUnavailable:
                if self._is_stale_usable() and key is not None:
                    logger.warning(
                        "jwks_refresh_failed_using_stale_key",
                        jwks_uri=self._jwks_uri,
                        kid=kid,
                        cache_age_seconds=self._cache_age_seconds(),
                    )
                    return key

                raise

            key = self._keys_by_kid.get(kid)
            if key is None:
                raise SigningKeyNotFound(f"Unknown kid {kid}")

        return key

    async def _refresh(self) -> None:

        payload = await self._get_json()

        keys_by_kid = self._parse_jwks(payload)

        self._keys_by_kid = keys_by_kid
        self._fetched_at_monotonic = time.monotonic()

        logger.info(
            "jwks_refreshed",
            jwks_uri=self._jwks_uri,
            key_count=len(self._keys_by_kid),
        )

    def _parse_jwks(self, payload: object) -> dict[str, PyJWK]:
        if not isinstance(payload, dict):
            raise JwksProviderUnavailable("JWKS payload has unexpected shape")

        try:
            jwk_set = PyJWKSet.from_dict(cast(dict[str, Any], payload))

        except (PyJWTError, KeyError, TypeError, ValueError) as exc:
            logger.error(
                "jwks_parse_failed",
                jwks_uri=self._jwks_uri,
                error_class=type(exc).__name__,
            )
            raise JwksProviderUnavailable("JWKS parse failed") from exc

        keys_by_kid: dict[str, PyJWK] = {}
        duplicate_kids: set[str] = set()

        for key in jwk_set.keys:
            kid = key.key_id
            if not kid:
                continue

            if not self._is_usable_signing_key(key):
                continue

            if kid in keys_by_kid:
                duplicate_kids.add(kid)
                continue

            keys_by_kid[kid] = key

        if duplicate_kids:
            logger.error(
                "jwks_duplicate_kids",
                jwks_uri=self._jwks_uri,
                duplicate_kids=sorted(duplicate_kids),
            )
            raise JwksProviderUnavailable("JWKS contains duplicate kid values")

        if not keys_by_kid:
            logger.error(
                "jwks_empty_keys",
                jwks_uri=self._jwks_uri,
            )
            raise JwksProviderUnavailable("JWKS contains no usable signing keys")

        return keys_by_kid

    async def _get_json(self) -> object:
        try:
            response = await self._http_client.get(
                self._jwks_uri,
                timeout=self._http_timeout_seconds,
            )
            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            logger.error(
                "jwks_fetch_http_status_error",
                jwks_uri=self._jwks_uri,
                status_code=exc.response.status_code,
            )
            raise JwksProviderUnavailable("jwks_fetch failed") from exc

        except httpx.RequestError as exc:
            logger.error(
                "jwks_fetch_request_error",
                jwks_uri=self._jwks_uri,
                error_class=type(exc).__name__,
            )
            raise JwksProviderUnavailable("jwks_fetch failed") from exc

        try:
            return response.json()

        except ValueError as exc:
            logger.error(
                "jwks_fetch_invalid_json_error",
                jwks_uri=self._jwks_uri,
                error_class=type(exc).__name__,
            )
            raise JwksProviderUnavailable("jwks_fetch returned invalid JSON") from exc

    def _is_usable_signing_key(self, key: PyJWK) -> bool:

        kid = key.key_id

        if self._allowed_key_types and key.key_type not in self._allowed_key_types:
            logger.debug(
                "jwks_key_skipped_by_key_type",
                jwks_uri=self._jwks_uri,
                kid=kid,
                key_type=key.key_type,
            )
            return False

        public_key_use = key.public_key_use
        if (
            public_key_use is not None
            and self._allowed_public_key_uses
            and public_key_use not in self._allowed_public_key_uses
        ):
            logger.debug(
                "jwks_key_skipped_by_public_key_use",
                jwks_uri=self._jwks_uri,
                kid=kid,
                public_key_use=public_key_use,
            )
            return False

        if self._allowed_algorithms:
            try:
                algorithm_name = key.algorithm_name
            except PyJWTError:
                logger.debug(
                    "jwks_key_skipped_by_missing_algorithm",
                    jwks_uri=self._jwks_uri,
                    kid=kid,
                )
                return False

            if algorithm_name not in self._allowed_algorithms:
                logger.debug(
                    "jwks_key_skipped_by_algorithm",
                    jwks_uri=self._jwks_uri,
                    kid=kid,
                    algorithm=algorithm_name,
                )
                return False

        return True

    def _is_stale(self) -> bool:
        cache_age = self._cache_age_seconds()

        if cache_age is None:
            return True

        return cache_age >= self._cache_ttl_seconds

    def _is_stale_usable(self) -> bool:
        cache_age = self._cache_age_seconds()

        if cache_age is None:
            return False

        return cache_age <= self._max_stale_seconds + self._cache_ttl_seconds

    def _cache_age_seconds(self) -> float | None:
        if self._fetched_at_monotonic is None:
            return None

        return time.monotonic() - self._fetched_at_monotonic

    def _enforce_forced_refresh_rate_limit(self, kid: str) -> None:
        now = time.monotonic()
        elapsed = now - self._last_forced_refresh_at_monotonic

        if elapsed < self._min_forced_refresh_interval_seconds:
            logger.info(
                "jwks_forced_refresh_rate_limited",
                jwks_uri=self._jwks_uri,
                kid=kid,
                elapsed=elapsed,
                min_interval_seconds=self._min_forced_refresh_interval_seconds,
            )
            raise SigningKeyNotFound("Unknown signing key")

        self._last_forced_refresh_at_monotonic = now
