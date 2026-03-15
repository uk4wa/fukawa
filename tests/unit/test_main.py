import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pydantic import PostgresDsn
from pytest_mock import MockerFixture

from pet.config.settings import Settings
from pet.main import build_lifespan


@pytest.fixture
def settings() -> Settings:
    return Settings(
        log_level="INFO",
        db_url=PostgresDsn("postgresql+asyncpg://user:pass@localhost:5432/pet"),
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
    connection = mocker.AsyncMock()
    connect_cm = mocker.AsyncMock()
    connect_cm.__aenter__.return_value = connection
    connect_cm.__aexit__.return_value = False
    engine.connect.return_value = connect_cm
    engine.dispose = mocker.AsyncMock()
    session_factory = mocker.Mock()

    mocker.patch("pet.main.configure_logging")
    mocker.patch("pet.main.create_engine", return_value=engine)
    create_session_maker = mocker.patch(
        "pet.main.create_session_maker", return_value=session_factory
    )

    async with LifespanManager(app):
        assert app.state.engine is engine
        assert app.state.session_factory is session_factory

    engine.connect.assert_called_once_with()
    connection.exec_driver_sql.assert_awaited_once_with("SELECT 1")
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
    connect_cm = mocker.AsyncMock()
    connect_cm.__aenter__.side_effect = OSError("db unavailable")
    connect_cm.__aexit__.return_value = False
    engine.connect.return_value = connect_cm
    engine.dispose = mocker.AsyncMock()

    mocker.patch("pet.main.configure_logging")
    mocker.patch("pet.main.create_engine", return_value=engine)
    create_session_maker = mocker.patch("pet.main.create_session_maker")

    with pytest.raises(OSError, match="db unavailable"):
        async with LifespanManager(app):
            pass

    create_session_maker.assert_not_called()
    engine.dispose.assert_awaited_once_with()
    assert not hasattr(app.state, "engine")
    assert not hasattr(app.state, "session_factory")
