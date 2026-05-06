class JwksProviderError(Exception):
    """Base JWKS provider error."""


class JwksProviderUnavailable(JwksProviderError):
    """JWKS provider cannot currently fetch or parse signing keys.

    Usually should be mapped to 503 or treated as auth subsystem unavailable.
    """


class SigningKeyNotFound(JwksProviderError):
    """Token references an unknown or unsupported signing key.

    Usually should be mapped to 401 Invalid Token.
    """
