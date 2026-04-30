from __future__ import annotations


class AuthError(Exception):
    """Base for all auth-layer failures."""

    error_code: str = "auth_error"
    description: str = "Authentication failed"


class AuthenticationError(AuthError):
    """Failed to authenticate the request. Maps to HTTP 401.

    The `error_code` value is also used as the RFC 6750 'error' field in
    WWW-Authenticate, e.g. invalid_request / invalid_token.
    """

    error_code = "invalid_token"
    description = "The access token is invalid"


class MissingToken(AuthenticationError):
    error_code = "invalid_request"
    description = "Authorization header with a Bearer token is required"


class InvalidToken(AuthenticationError):
    """Generic invalid-token; carries a description without leaking secrets."""

    def __init__(self, description: str = "The access token is invalid") -> None:
        super().__init__(description)
        self.description = description


class TokenVerificationUnavailable(AuthError):
    """Verifier could not reach JWKS / discovery. Fail closed -> 401.

    We treat this as 401 rather than 503 because the client cannot proceed
    without a verified token: returning 401 keeps the contract simple and
    avoids leaking infra state.
    """

    error_code = "temporarily_unavailable"
    description = "Token verification is temporarily unavailable"


class AuthorizationError(AuthError):
    """The request is authenticated but lacks required permissions. Maps to 403."""

    error_code = "insufficient_scope"
    description = "The access token does not grant the required permissions"


class InsufficientPermissions(AuthorizationError):
    def __init__(self, description: str = "Insufficient permissions") -> None:
        super().__init__(description)
        self.description = description
