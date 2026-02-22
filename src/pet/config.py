from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    debug: bool

    db_host: str
    db_name: str
    db_user: str
    # db_port: int
    db_password: SecretStr
    app_name: str

    @property
    def dsn(self):
        return (
            f"postgresql+asyncpg://{self.db_user}:"
            f"{self.db_password.get_secret_value()}@"
            f"{self.db_host}/"
            # f"{self.db_port}/"
            f"{self.db_name}"
        )

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


from functools import lru_cache


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore
