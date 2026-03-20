from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_api_organizations_create_success(client: AsyncClient, db_session: AsyncSession):
    name_json = {"name": "okname1"}
    response = await client.post("/orgs/", json=name_json)

    assert response.status_code == 201
    body = response.json()
    assert body["public_id"] is not None

    stmt = text("SELECT public_id FROM organizations WHERE name = :name")
    result = await db_session.execute(stmt, name_json)

    public_id = result.scalar_one()
    assert public_id is not None
    assert str(public_id) == body["public_id"]


@pytest.mark.asyncio
async def test_db_organizations_name_min_length_constraint(db_session: AsyncSession) -> None:
    stmt = text(
        """
        INSERT INTO organizations (public_id, name, created_at, updated_at)
        VALUES (CAST(:public_id AS uuid), :name, now(), now())
        """
    )

    with pytest.raises(IntegrityError, match="ck_organizations_name_min_len"):
        await db_session.execute(stmt, {"public_id": str(uuid4()), "name": "ab"})
        await db_session.commit()

    await db_session.rollback()
