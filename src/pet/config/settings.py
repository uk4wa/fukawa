from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from pet.config.logging import LogFormat

ROOT = Path(__file__).resolve().parents[3]
_APP_NAME = "pet-uk4wa"


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


class Settings(BaseSettings):
    app_name: str = _APP_NAME

    log_format: LogFormat = Field(default="json")
    log_level: str = Field(default="INFO")

    db: DatabaseSettings
    engine: EngineSettings = Field(default_factory=EngineSettings)
    session_maker: SessionMakerSettings = Field(default_factory=SessionMakerSettings)

    def __init__(self, **values: Any) -> None:
        super().__init__(**values)

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
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
