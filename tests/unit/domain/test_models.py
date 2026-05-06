from datetime import UTC, datetime
from uuid import UUID

from pet.domain.models import Organization, User
from pet.domain.value_objects import Name, PublicId


def test_organization_identity_is_based_on_public_id() -> None:
    public_id = PublicId.create(UUID("11111111-1111-1111-1111-111111111111"))

    left = Organization.create(
        public_id=public_id,
        name=Name.create("Acme"),
    )
    right = Organization.create(
        public_id=public_id,
        name=Name.create("Another legal name"),
    )

    assert left == right
    assert hash(left) == hash(right)


def test_user_created_without_updated_at_uses_created_at() -> None:
    created_at = datetime(2026, 5, 6, tzinfo=UTC)

    user = User.create(
        public_id=PublicId.create(UUID("11111111-1111-1111-1111-111111111111")),
        email="ukawa@example.com",
        username="ukawa",
        auth_issuer="http://auth.localhost:8080/realms/ukawa-pet",
        auth_subject="e128a400-8e98-4eae-9c5d-b5e464f61ac5",
        last_login_at=created_at,
        created_at=created_at,
    )

    assert user.updated_at == created_at
