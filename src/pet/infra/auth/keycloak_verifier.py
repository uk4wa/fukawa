from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any, Final

import jwt

from pet.app.auth.exc import InvalidToken, TokenVerificationUnavailable
from pet.app.auth.verifier import TokenVerifierAbstract
from pet.config.logging import get_logger
from pet.domain.auth import Principal
from pet.infra.auth.exc import JwksProviderUnavailable, SigningKeyNotFound
from pet.infra.auth.jwks import JWKSProvider

_REQUIRED_CLAIMS: Final = ["sub", "iss", "iat", "exp"]

logger = get_logger(__name__)


class KeycloakVerifier(TokenVerifierAbstract):
    def __init__(
        self,
        jwks_provider: JWKSProvider,
        issuer: str,
        audiences: Iterable[str],
        allowed_algorithms: Iterable[str],
        leeway_seconds: int,
    ) -> None:

        if not audiences:
            raise ValueError("audiences must not be empty")
        for alg in allowed_algorithms:
            if alg == "none":
                raise ValueError("Algorithm 'none' is not permitted")

        self._jwks = jwks_provider
        self._issuer = issuer
        self._audiences = tuple(dict.fromkeys(audiences))
        self._allowed_algorithms = tuple(dict.fromkeys(allowed_algorithms))
        self._leeway = leeway_seconds

    async def verify(self, raw_token: str) -> Principal:
        if not raw_token:
            raise InvalidToken("Empty Token")

        try:
            unverified_header = jwt.get_unverified_header(raw_token)
        except jwt.PyJWTError as exc:
            logger.info(
                "token_header_parse_failed",
                error_class=type(exc).__name__,
            )
            raise InvalidToken("Malformed token header") from exc

        kid = unverified_header.get("kid")
        if not isinstance(kid, str):
            raise InvalidToken("Token header is missing 'kid'")

        alg = unverified_header.get("alg")
        if not isinstance(alg, str) or alg not in self._allowed_algorithms:
            raise InvalidToken("Disallowed token algorithm")

        try:
            signing_key = await self._jwks.get_signing_key(kid)
        except SigningKeyNotFound as exc:
            raise InvalidToken("Token signed by an unknown key") from exc
        except JwksProviderUnavailable as exc:
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

        token_audience = _coerce_str_list(claims.get("aud"))
        azp = claims.get("azp")
        candidates = set(token_audience)

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
        return [x for x in value if isinstance(x, str)]
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


def _require_str_claim(claims: Mapping[str, Any], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value:
        raise InvalidToken(f"Token missing required claim: '{name}'")
    return value


def _optional_str_claim(claims: Mapping[str, Any], name: str) -> str | None:
    value = claims.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidToken(f"Token claim '{name}' must be a string")
    return value


def _build_principal(claims: Mapping[str, Any]) -> Principal:
    return Principal(
        subject=_require_str_claim(claims, "sub"),
        issuer=_require_str_claim(claims, "iss"),
        username=_require_str_claim(claims, "preferred_username"),
        email=_require_str_claim(claims, "email"),
        first_name=_optional_str_claim(claims, "given_name"),
        last_name=_optional_str_claim(claims, "family_name"),
        scopes=_extract_scopes(claims),
        realm_roles=_extract_realm_roles(claims),
        client_roles=_extract_client_roles(claims),
        raw_claims=MappingProxyType(dict(claims)),
    )


__all__ = ["KeycloakVerifier"]
