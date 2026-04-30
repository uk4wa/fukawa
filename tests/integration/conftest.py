from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.postgres import PostgresContainer  # type: ignore

from pet.app.auth.exc import InvalidToken
from pet.app.auth.verifier import TokenVerifier
from pet.config.settings import DatabaseSettings, KeycloakSettings, Settings
from pet.domain.auth.principal import Principal
from pet.main import create_app

TEST_TOKEN = "integration-test-token"
TEST_CLIENT_ID = "pet-backend"


class _AllScopesVerifier(TokenVerifier):
    """Returns a principal with every scope/role the integration suite needs."""

    _principal = Principal(
        subject="integration-test-user",
        username="integration",
        email="integration@test.local",
        scopes=frozenset({"organizations:write", "organizations:read"}),
        realm_roles=frozenset({"admin", "user"}),
    )

    async def verify(self, raw_token: str) -> Principal:
        if raw_token != TEST_TOKEN:
            raise InvalidToken("Unknown integration test token")
        return self._principal


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:18", driver="asyncpg") as container:
        yield container


@pytest.fixture(scope="session")
def migrated_postgres_db(
    postgres_container: PostgresContainer,
) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_container.get_connection_url())
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def test_settings(
    postgres_container: PostgresContainer,
    migrated_postgres_db: None,
) -> Settings:
    return Settings(
        app_name="pet-uk4wa",
        db=DatabaseSettings(
            driver="postgresql+asyncpg",
            host=postgres_container.get_container_host_ip(),
            port=int(postgres_container.get_exposed_port(5432)),
            user=postgres_container.username,
            password=SecretStr(postgres_container.password),
            name=postgres_container.dbname,
        ),
        keycloak=KeycloakSettings(
            issuer_url="http://test/realms/pet",  # type: ignore[arg-type]
            client_id=TEST_CLIENT_ID,
            audience=[TEST_CLIENT_ID],
        ),
    )


@pytest_asyncio.fixture
async def app(
    test_settings: Settings,
) -> AsyncIterator[FastAPI]:
    app_instance = create_app(
        settings=test_settings,
        token_verifier=_AllScopesVerifier(),
    )
    async with LifespanManager(app_instance):
        yield app_instance


@pytest_asyncio.fixture
async def client(
    app: FastAPI,
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    ) as http_client:
        yield http_client


@pytest_asyncio.fixture
async def db_session(
    app: FastAPI,
) -> AsyncIterator[AsyncSession]:
    async with app.state.session_factory() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def clean_db(app: FastAPI) -> None:
    async with app.state.session_factory() as session:
        await session.execute(
            text(
                """
                TRUNCATE TABLE
                    memberships,
                    tasks,
                    projects,
                    organizations,
                    users
                RESTART IDENTITY CASCADE
                """
            )
        )
        await session.commit()
