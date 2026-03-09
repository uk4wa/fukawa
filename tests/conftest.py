import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, Mock
from pytest_mock import MockerFixture
from pet.infra.transaction_executor import TransactionExecutor

from fastapi import FastAPI

from httpx import ASGITransport, AsyncClient
from asgi_lifespan import LifespanManager
from testcontainers.postgres import PostgresContainer

from alembic.config import Config
from alembic import command
from typing import AsyncIterator, Iterator
from sqlalchemy.ext.asyncio import AsyncSession

from pet.main import create_app
from pet.config import DatabaseSettings, Settings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:18", driver="asyncpg") as p:
        yield p


@pytest.fixture(scope="session")
def postgres_url(postgres_container: PostgresContainer) -> str:
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def migrate_db(postgres_url: str):
    config = Config(str("alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(config, "head")
    return postgres_url


@pytest.fixture(scope="session")
def test_settings(postgres_url: str, migrate_db: str):
    return Settings(  # type: ignore
        debug=True,
        app_name="pet-uk4wa",
        db_url=postgres_url,
        # db=DatabaseSettings(
        #     host=postgres_container.get_container_host_ip(),
        #     port=int(postgres_container.get_exposed_port(5432)),
        #     user=postgres_container.POSTGRES_USER,
        #     password=postgres_container.POSTGRES_PASSWORD,
        #     name=postgres_container.POSTGRES_DB,
        # ),
    )


@pytest_asyncio.fixture(scope="function")
async def app(test_settings: Settings):
    app_instance = create_app(settings=test_settings)
    async with LifespanManager(app_instance):
        yield app_instance


@pytest_asyncio.fixture(scope="function")
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=True),
        base_url="http://test",
        # raise_server_exceptions=True,
    ) as http_client:
        yield http_client


@pytest_asyncio.fixture(scope="function")
async def db_session(app: FastAPI, test_settings) -> AsyncIterator[AsyncSession]:
    async with app.state.session_factory() as session:
        yield session


@pytest.fixture
def uow_mock(mocker: MockerFixture) -> AsyncMock:
    uow = mocker.MagicMock()
    uow.commit = mocker.AsyncMock()
    uow.__aenter__ = mocker.AsyncMock(return_value=uow)
    uow.__aexit__ = mocker.AsyncMock(return_value=False)
    return uow


@pytest.fixture
def uow_factory(uow_mock: AsyncMock, mocker: MockerFixture) -> Mock:
    return mocker.Mock(return_value=uow_mock)


@pytest.fixture
def executor(uow_factory: Mock) -> TransactionExecutor:
    return TransactionExecutor(uow_factory=uow_factory)
