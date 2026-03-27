from unicodedata import normalize
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pet.app.exc import VALIDATION_ERROR_TITLE, AppErrorCode


@pytest.mark.asyncio
@pytest.mark.integration
async def test_api_organizations_create_success(
    client: AsyncClient,
    db_session: AsyncSession,
):
    name_json = {"name": "okname1"}
    response = await client.post("/orgs/", json=name_json)

    assert response.status_code == 201
    body = response.json()
    assert body["public_id"] is not None

    stmt = text("SELECT public_id, name_canonical FROM organizations WHERE name = :name")
    result = await db_session.execute(stmt, name_json)

    public_id, name_canonical = result.one()
    assert public_id is not None
    assert str(public_id) == body["public_id"]
    assert name_canonical == "okname1"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_api_organizations_create_rejects_casefold_duplicate(
    client: AsyncClient,
) -> None:
    first = await client.post("/orgs/", json={"name": "Acme"})
    second = await client.post("/orgs/", json={"name": "acme"})

    assert first.status_code == 201
    assert second.status_code == 409

    body = second.json()
    assert body["code"] == "organization_name_taken"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_api_organizations_create_rejects_unicode_casefold_duplicate(
    client: AsyncClient,
) -> None:
    first = await client.post("/orgs/", json={"name": "Stra\u00dfe"})
    second = await client.post("/orgs/", json={"name": "STRASSE"})

    assert first.status_code == 201
    assert second.status_code == 409

    body = second.json()
    assert body["code"] == "organization_name_taken"


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize(
    ("name", "expected_detail"),
    [
        (65 * "a", "Name is too long"),
        ("sm", "Name is too short"),
        ("", "Name cannot be empty"),
    ],
)
async def test_api_organizations_create_returns_422_for_domain_validation(
    client: AsyncClient,
    name: str,
    expected_detail: str,
) -> None:
    response = await client.post("/orgs/", json={"name": name})

    assert response.status_code == 422

    body = response.json()
    assert body["title"] == VALIDATION_ERROR_TITLE
    assert body["detail"] == expected_detail
    assert body["code"] == AppErrorCode.VALIDATION


@pytest.mark.asyncio
@pytest.mark.integration
async def test_api_organizations_create_normalizes_unicode_name_to_nfc(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    original = "A\u0308rger Stra\u00dfe"
    response = await client.post("/orgs/", json={"name": original})

    assert response.status_code == 201

    stmt = text("SELECT name FROM organizations WHERE public_id = CAST(:public_id AS uuid)")
    result = await db_session.execute(stmt, {"public_id": response.json()["public_id"]})
    (name,) = result.one()

    assert name == normalize("NFC", original)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_api_organizations_create_returns_422_for_canonical_length_validation(
    client: AsyncClient,
) -> None:
    response = await client.post("/orgs/", json={"name": "\u00df" * 64})

    assert response.status_code == 422

    body = response.json()
    assert body["title"] == VALIDATION_ERROR_TITLE
    assert body["detail"] == "Name is too long"
    assert body["code"] == AppErrorCode.VALIDATION


@pytest.mark.asyncio
@pytest.mark.integration
async def test_api_openapi_describes_organization_name_contract(
    client: AsyncClient,
) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()["components"]["schemas"]["CreateOrgDtoIn"]
    name_schema = schema["properties"]["name"]

    assert name_schema["type"] == "string"
    assert "trimmed and normalized to NFC" in name_schema["description"]
    assert "canonical form must not exceed 64 characters" in name_schema["description"]


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("payload", [{}, {"name": 123}])
async def test_api_organizations_create_returns_422_for_request_validation(
    client: AsyncClient,
    payload: dict[str, object],
) -> None:
    response = await client.post("/orgs/", json=payload)

    assert response.status_code == 422

    body = response.json()
    assert body["title"] == VALIDATION_ERROR_TITLE
    assert body["detail"] == "Request validation failed"
    assert body["code"] == AppErrorCode.VALIDATION


@pytest.mark.asyncio
@pytest.mark.integration
async def test_db_organizations_name_min_length_constraint(
    db_session: AsyncSession,
) -> None:
    stmt = text(
        """
        INSERT INTO organizations (public_id, name, created_at, updated_at)
        VALUES (CAST(:public_id AS uuid), :name, now(), now())
        """
    )

    with pytest.raises(IntegrityError, match="ck_organizations_name_min_len"):
        await db_session.execute(
            stmt,
            {
                "public_id": str(uuid4()),
                "name": "ab",
            },
        )
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_db_organizations_name_canonical_is_generated(
    db_session: AsyncSession,
) -> None:
    stmt = text(
        """
        INSERT INTO organizations (public_id, name, name_canonical, created_at, updated_at)
        VALUES (CAST(:public_id AS uuid), :name, :name_canonical, now(), now())
        """
    )

    with pytest.raises(DBAPIError, match="generated column"):
        await db_session.execute(
            stmt,
            {
                "public_id": str(uuid4()),
                "name": "Acme",
                "name_canonical": "trash",
            },
        )
        await db_session.commit()

    await db_session.rollback()
