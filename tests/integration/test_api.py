import pytest
from httpx import ASGITransport, AsyncClient
from asgi_lifespan import LifespanManager

from pet.main import create_app


@pytest.fixture
async def app():
    app_instance = create_app()
    async with LifespanManager(app_instance):
        yield app_instance


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.anyio
async def test_api_organizations_create_success(client: AsyncClient):
    response = await client.post("/orgs/", json={"name": "okname1"})

    assert response.status_code == 201
    body = response.json()
    assert body["public_id"] is not None
