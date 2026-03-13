from functools import cached_property, lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[2]
APP_NAME = "pet-uk4wa"


class DatabaseSettings(BaseModel):
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
    debug: bool = False
    app_name: str = APP_NAME

    db_url: PostgresDsn | None = None
    db: DatabaseSettings | None = None
    engine: EngineSettings = Field(default_factory=EngineSettings)
    session_maker: SessionMakerSettings = Field(default_factory=SessionMakerSettings)

    @cached_property
    def dsn(self) -> str:
        if self.db_url is not None:
            return str(self.db_url)

        if self.db is not None:
            return URL.create(
                drivername="postgresql+asyncpg",
                username=self.db.user,
                password=self.db.password.get_secret_value(),
                host=self.db.host,
                port=self.db.port,
                database=self.db.name,
            ).render_as_string(hide_password=False)

        raise RuntimeError("Database URL is not Initialized")

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
