from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any, Final

import jwt

from pet.app.auth.exc import (
    InvalidToken,
    TokenVerificationUnavailable,
)
from pet.app.auth.verifier import TokenVerifier
from pet.config.logging import get_logger
from pet.domain.auth.principal import Principal
from pet.infra.auth.jwks import JwksProvider

logger = get_logger(__name__)

_REQUIRED_CLAIMS: Final = ["exp", "iat", "iss", "sub"]


class KeycloakTokenVerifier(TokenVerifier):
    """JWT verifier for Keycloak access tokens.

    Trust model:
      * Signature is verified against the configured JWKS — no unsigned tokens.
      * Algorithms are restricted to the configured allow-list (RS256 by default).
      * `iss` must equal the configured issuer.
      * Audience is satisfied if any of the configured audiences appears in
        `aud` OR matches Keycloak's `azp` claim. This matches Keycloak's
        common token shape where the access token's `aud` may be empty and
        `azp` carries the client_id.
      * `exp`, `nbf`, `iat` are validated by PyJWT with the configured leeway.

    Failures: `InvalidToken` for any token-side problem (bad sig, wrong iss,
    expired, etc.); `TokenVerificationUnavailable` for JWKS / discovery issues.
    """

    def __init__(
        self,
        *,
        jwks: JwksProvider,
        issuer: str,
        audiences: Iterable[str],
        allowed_algorithms: Iterable[str],
        leeway_seconds: int,
    ) -> None:
        self._jwks = jwks
        self._issuer = issuer
        self._audiences = tuple(dict.fromkeys(audiences))
        self._allowed_algorithms = tuple(dict.fromkeys(allowed_algorithms))
        self._leeway = leeway_seconds

        if not self._allowed_algorithms:
            raise ValueError("allowed_algorithms must not be empty")
        for alg in self._allowed_algorithms:
            if alg.lower() == "none":
                raise ValueError("Algorithm 'none' is not permitted")

    async def verify(self, raw_token: str) -> Principal:
        if not raw_token:
            raise InvalidToken("Empty token")

        try:
            unverified_header = jwt.get_unverified_header(raw_token)
        except jwt.PyJWTError as exc:
            logger.info("token_header_parse_failed", error_class=type(exc).__name__)
            raise InvalidToken("Malformed token header") from exc

        kid = unverified_header.get("kid")
        if not isinstance(kid, str):
            raise InvalidToken("Token header is missing 'kid'")

        alg = unverified_header.get("alg")
        if not isinstance(alg, str) or alg not in self._allowed_algorithms:
            raise InvalidToken("Disallowed token algorithm")

        try:
            signing_key = await self._jwks.get_signing_key(kid)
        except TokenVerificationUnavailable:
            raise
        except InvalidToken:
            raise
        except Exception as exc:  # defence in depth
            logger.error("jwks_lookup_unexpected_error", error_class=type(exc).__name__)
            raise TokenVerificationUnavailable("JWKS lookup failed") from exc

        try:
            claims: dict[str, Any] = jwt.decode(
                raw_token,
                key=signing_key.key,
                algorithms=list(self._allowed_algorithms),
                issuer=self._issuer,
                leeway=self._leeway,
                options={
                    "require": _REQUIRED_CLAIMS,
                    "verify_aud": False,
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise InvalidToken("Token has expired") from exc
        except jwt.ImmatureSignatureError as exc:
            raise InvalidToken("Token is not yet valid") from exc
        except jwt.InvalidIssuerError as exc:
            raise InvalidToken("Invalid token issuer") from exc
        except jwt.InvalidSignatureError as exc:
            raise InvalidToken("Invalid token signature") from exc
        except jwt.MissingRequiredClaimError as exc:
            raise InvalidToken("Token is missing required claims") from exc
        except jwt.InvalidAlgorithmError as exc:
            raise InvalidToken("Disallowed token algorithm") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidToken("Invalid token") from exc

        self._validate_audience(claims)

        return _build_principal(claims)

    def _validate_audience(self, claims: Mapping[str, Any]) -> None:
        if not self._audiences:
            return

        token_audiences = _coerce_str_list(claims.get("aud"))
        azp = claims.get("azp")
        candidates = set(token_audiences)
        if isinstance(azp, str) and azp:
            candidates.add(azp)

        for expected in self._audiences:
            if expected in candidates:
                return

        raise InvalidToken("Invalid token audience")


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def _extract_scopes(claims: Mapping[str, Any]) -> frozenset[str]:
    raw = claims.get("scope")
    if isinstance(raw, str) and raw:
        return frozenset(raw.split())

    scp = claims.get("scp")
    if isinstance(scp, list):
        return frozenset(s for s in scp if isinstance(s, str))
    return frozenset()


def _extract_realm_roles(claims: Mapping[str, Any]) -> frozenset[str]:
    realm_access = claims.get("realm_access")
    if not isinstance(realm_access, dict):
        return frozenset()
    roles = realm_access.get("roles")
    if not isinstance(roles, list):
        return frozenset()
    return frozenset(r for r in roles if isinstance(r, str))


def _extract_client_roles(claims: Mapping[str, Any]) -> Mapping[str, frozenset[str]]:
    resource_access = claims.get("resource_access")
    if not isinstance(resource_access, dict):
        return MappingProxyType({})

    out: dict[str, frozenset[str]] = {}
    for client, body in resource_access.items():
        if not isinstance(client, str) or not isinstance(body, dict):
            continue
        roles = body.get("roles")
        if isinstance(roles, list):
            out[client] = frozenset(r for r in roles if isinstance(r, str))
    return MappingProxyType(out)


def _build_principal(claims: Mapping[str, Any]) -> Principal:
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidToken("Token is missing 'sub'")

    username = claims.get("preferred_username")
    email = claims.get("email")

    return Principal(
        subject=subject,
        username=username if isinstance(username, str) else None,
        email=email if isinstance(email, str) else None,
        realm_roles=_extract_realm_roles(claims),
        client_roles=_extract_client_roles(claims),
        scopes=_extract_scopes(claims),
        raw_claims=MappingProxyType(dict(claims)),
    )


__all__ = ["KeycloakTokenVerifier"]
