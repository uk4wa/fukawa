from datetime import UTC, datetime
from uuid import UUID

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from pet.domain.models import User
from pet.domain.value_objects import PublicId
from pet.infra.sqla.db.exc import PersistenceError, PersistenceErrorKind
from pet.infra.sqla.db.repos import SQLAlchemyUsersRepo


@pytest.mark.asyncio
async def test_users_repo_upsert_translates_sqla_error(mocker: MockerFixture) -> None:
    session = mocker.AsyncMock(spec=AsyncSession)
    session.execute.side_effect = SQLAlchemyError("db failed")
    repo = SQLAlchemyUsersRepo(session)
    now = datetime(2026, 5, 6, tzinfo=UTC)
    user = User.create(
        public_id=PublicId.create(UUID("11111111-1111-1111-1111-111111111111")),
        email="ukawa@example.com",
        username="ukawa",
        auth_issuer="http://auth.localhost:8080/realms/ukawa-pet",
        auth_subject="e128a400-8e98-4eae-9c5d-b5e464f61ac5",
        last_login_at=now,
        created_at=now,
    )

    with pytest.raises(PersistenceError) as exc_info:
        await repo.upsert(user)

    assert exc_info.value.kind == PersistenceErrorKind.UNKNOWN
