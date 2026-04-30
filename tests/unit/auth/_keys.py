"""Lightweight in-test RSA keypair + JWS signer.

Goal: produce valid RS256 access tokens without depending on Keycloak.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _b64u(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@dataclass
class RsaTestKey:
    kid: str
    private_pem: bytes
    public_jwk: dict[str, Any]

    def sign(self, claims: dict[str, Any], *, algorithm: str = "RS256") -> str:
        return jwt.encode(
            claims,
            key=self.private_pem,
            algorithm=algorithm,
            headers={"kid": self.kid},
        )


def make_rsa_key(*, kid: str = "test-key", key_size: int = 2048) -> RsaTestKey:
    private = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_numbers = private.public_key().public_numbers()
    jwk: dict[str, Any] = {
        "kty": "RSA",
        "kid": kid,
        "alg": "RS256",
        "use": "sig",
        "n": _b64u(public_numbers.n),
        "e": _b64u(public_numbers.e),
    }
    return RsaTestKey(kid=kid, private_pem=private_pem, public_jwk=jwk)
