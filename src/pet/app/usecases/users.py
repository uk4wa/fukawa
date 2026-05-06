from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pet.domain.auth import Principal
from pet.domain.models import User
from pet.domain.uow import UnitOfWork
from pet.domain.value_objects import PublicId


async def provision_user_from_claims(
    uow: UnitOfWork,
    principal: Principal,
    uuid_gen: Callable[[], UUID] = uuid4,
) -> tuple[User, bool]:
    now = datetime.now(UTC)

    existing = await uow.users.get_by_auth_identity(
        issuer=principal.issuer,
        subject=principal.subject,
    )

    public_id = existing.public_id if existing is not None else PublicId(uuid_gen())
    created_at = existing.created_at if existing is not None else now

    user = User.create(
        public_id=public_id,
        auth_issuer=principal.issuer,
        auth_subject=principal.subject,
        email=principal.email,
        username=principal.username,
        first_name=principal.first_name,
        last_name=principal.last_name,
        last_login_at=now,
        created_at=created_at,
        updated_at=now,
    )

    return (await uow.users.upsert(user), existing is None)
