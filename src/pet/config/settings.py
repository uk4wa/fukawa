from functools import cached_property, lru_cache
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from pet.config.exc import unsapported_log_level_value_error

_ROOT = Path(__file__).resolve().parents[3]
_APP_NAME = "pet-uk4wa"

_VALID_LOG_LEVELS: Final[frozenset[str]] = frozenset(
    {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
)

type LogFormat = Literal["json", "console"]


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


class SessionMakerSettings(BaseModel):
    expire_on_commit: bool = False
    autoflush: bool = True


class Settings(BaseSettings):
    log_level: str
    log_format: LogFormat = "json"
    app_name: str = _APP_NAME

    db: DatabaseSettings
    engine: EngineSettings = Field(default_factory=EngineSettings)
    session_maker: SessionMakerSettings = Field(default_factory=SessionMakerSettings)

    @field_validator("db_url", mode="before")
    @classmethod
    def normalize_db_url(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("log_level")
    @classmethod
    def validator_log_level(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("level can not be empty")
        if v not in _VALID_LOG_LEVELS:
            raise unsapported_log_level_value_error(v, _VALID_LOG_LEVELS)
        return v

    @cached_property
    def dsn(self) -> str:
        return URL.create(
            drivername=self.db.driver,
            username=self.db.user,
            password=self.db.password.get_secret_value(),
            host=self.db.host,
            port=self.db.port,
            database=self.db.name,
        ).render_as_string(hide_password=False)

    model_config = SettingsConfigDict(
        env_file=_ROOT / ".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore
