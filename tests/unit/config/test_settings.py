from pet.config.settings import Settings


def test_settings_treats_empty_db_url_as_none() -> None:
    settings = Settings(log_level="INFO", db_url="")

    assert settings.db_url is None
