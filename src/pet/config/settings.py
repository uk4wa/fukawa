from __future__ import annotations

from functools import cached_property, lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from pet.config.logging import LogFormat

ROOT = Path(__file__).resolve().parents[3]
_APP_NAME = "pet-uk4wa"


def _build_oidc_discovery_url(issuer_url: str) -> str:
    """Per OIDC Discovery 1.0 §4: discovery doc lives at <issuer>/.well-known/openid-configuration."""
    return f"{issuer_url.rstrip('/')}/.well-known/openid-configuration"


class DatabaseSettings(BaseModel):
    driver: str
    host: str
    name: str
    user: str
    port: int
    password: SecretStr


class EngineSettings(BaseModel):
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20
    pool_pre_ping: bool = True


class SessionMakerSettings(BaseModel):
    expire_on_commit: bool = False
    autoflush: bool = True


class KeycloakSettings(BaseModel):
    """OAuth 2.1 / OIDC Resource Server configuration.

    The service is a pure Resource Server: it never holds the client secret,
    never performs login redirects, never calls the token endpoint. It only
    validates Bearer JWT access tokens issued by Keycloak through JWKS.
    """

    issuer_url: AnyHttpUrl = Field(
        description="OIDC issuer URL, e.g. https://auth.example.com/realms/myrealm"
    )
    internal_issuer_url: AnyHttpUrl | None = Field(
        default=None,
        description=(
            "Optional issuer URL reachable from this service for OIDC metadata/JWKS "
            "fetches when the public issuer hostname is not routable inside the runtime "
            "network, e.g. Docker Compose."
        ),
    )
    audience: list[str] = Field(
        default_factory=list,
        description=(
            "Expected audiences. Keycloak access tokens commonly carry the "
            "client_id in 'azp'. Listing the client_id here covers both the "
            "'aud' claim and the Keycloak 'azp'."
        ),
    )
    client_id: str = Field(
        description="Resource Server's Keycloak client_id (used to extract resource_access roles)."
    )
    allowed_algorithms: list[str] = Field(
        default_factory=lambda: ["RS256"],
        description="Allowed JWS algorithms. Keep RS256/ES256 only; never include 'none' or HS*.",
    )
    jwks_cache_ttl_seconds: int = Field(
        default=300,
        ge=0,
        description="How long to cache JWKS before re-fetching. JWKS is also refreshed on unknown kid.",
    )
    leeway_seconds: int = Field(
        default=30,
        ge=0,
        description="Allowed clock skew when validating exp/nbf/iat.",
    )
    http_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        description="HTTP timeout for OIDC discovery / JWKS fetch.",
    )

    @field_validator("allowed_algorithms")
    @classmethod
    def _reject_unsafe_algorithms(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("KEYCLOAK__ALLOWED_ALGORITHMS must not be empty")
        normalized = [a.strip() for a in value]
        for alg in normalized:
            if alg.lower() == "none":
                raise ValueError("Algorithm 'none' is not permitted")
        return normalized

    @field_validator("audience")
    @classmethod
    def _strip_audience(cls, value: list[str]) -> list[str]:
        return [a.strip() for a in value if a and a.strip()]

    @cached_property
    def issuer(self) -> str:
        """Canonical issuer string used for token 'iss' comparison.

        Pydantic's AnyHttpUrl renders with a trailing slash; Keycloak's 'iss'
        claim does not. We normalise here so equality comparison is exact.
        """
        return str(self.issuer_url).rstrip("/")

    @cached_property
    def internal_issuer(self) -> str:
        return str(self.internal_issuer_url or self.issuer_url).rstrip("/")

    @cached_property
    def discovery_url(self) -> str:
        return _build_oidc_discovery_url(self.internal_issuer)


class Settings(BaseSettings):
    app_name: str = _APP_NAME

    log_format: LogFormat = Field(default="json")
    log_level: str = Field(default="INFO")

    db: DatabaseSettings
    engine: EngineSettings = Field(default_factory=EngineSettings)
    session_maker: SessionMakerSettings = Field(default_factory=SessionMakerSettings)
    keycloak: KeycloakSettings

    @cached_property
    def db_url(self) -> URL:
        return URL.create(
            drivername=self.db.driver,
            username=self.db.user,
            password=self.db.password.get_secret_value(),
            host=self.db.host,
            port=self.db.port,
            database=self.db.name,
        )

    @cached_property
    def db_dsn(self) -> str:
        return self.db_url.render_as_string(hide_password=False)

    @cached_property
    def safe_db_dsn(self) -> str:
        return self.db_url.render_as_string(hide_password=True)

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore
