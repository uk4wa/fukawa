import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pydantic import SecretStr
from pytest_mock import MockerFixture

from pet.config.settings import DatabaseSettings, Settings
from pet.main import build_lifespan


@pytest.fixture
def settings() -> Settings:
    return Settings(
        log_level="INFO",
        db=DatabaseSettings(
            driver="postgresql+asyncpg",
            host="localhost",
            name="pet",
            user="user",
            port=5432,
            password=SecretStr("pass"),
        ),
    )


@pytest_asyncio.fixture
async def app(settings: Settings) -> FastAPI:
    return FastAPI(lifespan=build_lifespan(settings))


@pytest.mark.asyncio
async def test_build_lifespan_checks_db_connection_on_startup(
    app: FastAPI,
    mocker: MockerFixture,
):
    engine = mocker.Mock()
    engine.dispose = mocker.AsyncMock()
    session_factory = mocker.Mock()

    mocker.patch("pet.main.configure_logging")
    mocker.patch("pet.main.create_engine", return_value=engine)
    ping_engine = mocker.patch("pet.main.ping_engine", autospec=True)
    create_session_maker = mocker.patch(
        "pet.main.create_session_maker", return_value=session_factory
    )

    async with LifespanManager(app):
        assert app.state.engine is engine
        assert app.state.session_factory is session_factory

    ping_engine.assert_awaited_once_with(engine)
    create_session_maker.assert_called_once_with(
        bind=engine,
        autoflush=True,
        expire_on_commit=False,
    )
    engine.dispose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_build_lifespan_fails_startup_when_db_connection_check_fails(
    app: FastAPI,
    mocker: MockerFixture,
):
    engine = mocker.Mock()
    engine.dispose = mocker.AsyncMock()

    mocker.patch("pet.main.configure_logging")
    mocker.patch("pet.main.create_engine", return_value=engine)
    mocker.patch("pet.main.ping_engine", side_effect=OSError("db unavailable"), autospec=True)
    create_session_maker = mocker.patch("pet.main.create_session_maker")

    with pytest.raises(OSError, match="db unavailable"):
        async with LifespanManager(app):
            pass

    create_session_maker.assert_not_called()
    engine.dispose.assert_awaited_once_with()
    assert not hasattr(app.state, "engine")
    assert not hasattr(app.state, "session_factory")
