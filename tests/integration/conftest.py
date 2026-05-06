from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager
from docker.errors import DockerException
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.postgres import PostgresContainer  # type: ignore

from pet.api.auth import get_current_principal
from pet.config.settings import DatabaseSettings, KeycloakSettings, Settings
from pet.domain.auth import Principal
from pet.main import create_app


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    try:
        with PostgresContainer("postgres:18", driver="asyncpg") as container:
            yield container
    except DockerException as exc:
        pytest.skip(f"Docker is required for integration tests: {exc}")


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
            hostname="http://auth.test",
            issuer_url="http://auth.test/realms/test",
            jwks_uri="http://auth.test/realms/test/protocol/openid-connect/certs",
            client_id="pet-backend",
        ),
    )


@pytest_asyncio.fixture
async def app(
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[FastAPI]:
    class StubAuthClient:
        async def aclose(self) -> None:
            pass

    class StubVerifier:
        async def verify(self, raw_token: str) -> Principal:
            return _test_principal()

    async def build_stub_auth_components(_settings: KeycloakSettings):
        return StubAuthClient(), object(), StubVerifier()

    async def override_current_principal() -> Principal:
        return _test_principal()

    monkeypatch.setattr("pet.main.build_auth_components", build_stub_auth_components)

    app_instance = create_app(settings=test_settings)
    app_instance.dependency_overrides[get_current_principal] = override_current_principal
    async with LifespanManager(app_instance):
        yield app_instance


@pytest_asyncio.fixture
async def client(
    app: FastAPI,
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
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


def _test_principal() -> Principal:
    return Principal(
        subject="11111111-1111-1111-1111-111111111111",
        issuer="http://auth.test/realms/test",
        username="ukawa",
        email="ukawa@example.com",
        first_name="ukawa",
        last_name="ukawa",
        scopes=frozenset({"organizations:write"}),
    )
