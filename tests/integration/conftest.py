from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.postgres import PostgresContainer  # type: ignore

from pet.config.settings import DatabaseSettings, Settings
from pet.main import create_app


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:18", driver="asyncpg") as container:
        yield container


@pytest.fixture(scope="session")
def migrated_postgres_db(postgres_container: PostgresContainer) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_container.get_connection_url())
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def test_settings(
    postgres_container: PostgresContainer,
    migrated_postgres_db: None,
) -> Settings:
    return Settings(
        log_level="DEBUG",
        app_name="pet-uk4wa",
        db=DatabaseSettings(
            driver="postgresql+asyncpg",
            host=postgres_container.get_container_host_ip(),
            port=int(postgres_container.get_exposed_port(5432)),
            user=postgres_container.username,
            password=SecretStr(postgres_container.password),
            name=postgres_container.dbname,
        ),
    )


@pytest_asyncio.fixture(scope="function")
async def app(test_settings: Settings) -> AsyncIterator[FastAPI]:
    app_instance = create_app(settings=test_settings)
    async with LifespanManager(app_instance):
        yield app_instance


@pytest_asyncio.fixture(scope="function")
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as http_client:
        yield http_client


@pytest_asyncio.fixture(scope="function")
async def db_session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    async with app.state.session_factory() as session:
        yield session
