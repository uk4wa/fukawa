from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, SecretStr, Field
from functools import lru_cache
from pathlib import Path


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

    db_url: str | None = None
    db: DatabaseSettings | None = None
    engine: EngineSettings = Field(default_factory=EngineSettings)
    session_maker: SessionMakerSettings = Field(default_factory=SessionMakerSettings)

    @property
    def dsn(self) -> str:
        if self.db_url is not None:
            return self.db_url

        if self.db is not None:
            return (
                f"postgresql+asyncpg://{self.db.user}:"
                f"{self.db.password.get_secret_value()}@"
                f"{self.db.host}:"
                f"{self.db.port}/"
                f"{self.db.name}"
            )
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
