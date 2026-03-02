from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, SecretStr
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


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
    debug: bool
    app_name: str

    db: DatabaseSettings
    engine: EngineSettings
    session_maker: SessionMakerSettings

    @property
    def dsn(self):
        return (
            f"postgresql+asyncpg://{self.db.user}:"
            f"{self.db.password.get_secret_value()}@"
            f"{self.db.host}:"
            f"{self.db.port}/"
            f"{self.db.name}"
        )

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
