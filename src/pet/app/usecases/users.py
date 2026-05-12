from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pet.config.logging import get_logger
from pet.domain.auth import Principal
from pet.domain.models import User
from pet.domain.uow import UnitOfWork
from pet.domain.value_objects import PublicId

logger = get_logger(__name__)


async def provision_user_from_claims(
    uow: UnitOfWork,
    principal: Principal,
    uuid_gen: Callable[[], UUID] = uuid4,
) -> tuple[User, bool]:
    now = datetime.now(UTC)
    public_id = PublicId(uuid_gen())

    logger.debug(
        "provision_user_started",
        public_id=public_id.value,
    )

    user = User.create(
        public_id=public_id,
        auth_issuer=principal.issuer,
        auth_subject=principal.subject,
        email=principal.email,
        username=principal.username,
        first_name=principal.first_name,
        last_name=principal.last_name,
        last_login_at=now,
        created_at=now,
        updated_at=now,
    )

    logger.debug(
        "provision_user_staged",
        user_public_id=public_id.value,
    )

    user, inserted = await uow.users.upsert(user)

    logger.debug(
        "provision_user_finished",
        created=inserted,
    )

    return user, inserted
