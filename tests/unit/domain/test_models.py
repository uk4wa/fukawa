from uuid import UUID

from pet.domain.models import Organization
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
