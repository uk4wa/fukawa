from __future__ import annotations

from typing import Protocol

from pet.domain.auth.principal import Principal


class TokenVerifier(Protocol):
    """Verifies a raw Bearer access token and returns a Principal.

    Implementations MUST:
      * verify the JWS signature against trusted keys (e.g. JWKS);
      * validate iss, aud/azp, exp, nbf, iat with explicit leeway;
      * restrict the algorithm set (no 'none', no HS* unless explicitly desired);
      * fail closed: any uncertainty raises AuthenticationError.
    """

    async def verify(self, raw_token: str) -> Principal: ...
