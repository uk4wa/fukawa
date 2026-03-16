from pydantic import SecretStr

from pet.config.settings import DatabaseSettings, Settings


def test_settings_normalizes_log_level() -> None:
    settings = Settings(
        log_level=" info ",
        db=DatabaseSettings(
            driver="postgresql+asyncpg",
            host="localhost",
            name="pet",
            user="user",
            port=5432,
            password=SecretStr("pass"),
        ),
    )

    assert settings.log_level == "INFO"
