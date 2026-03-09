import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_api_organizations_create_success(
    client: AsyncClient, db_session: AsyncSession
):
    params_json = {"name": "okname1"}
    response = await client.post("/orgs/", json=params_json)

    assert response.status_code == 201
    body = response.json()
    assert body["public_id"] is not None

    stmt = text("SELECT public_id FROM organizations WHERE name = :name")
    result = await db_session.execute(stmt, params_json)

    row = result.fetchone()
    assert row is not None
    assert str(row.public_id) == body["public_id"]
