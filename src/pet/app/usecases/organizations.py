from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from pet.app.errors import not_found
from pet.config.logging import get_logger
from pet.domain.auth import Principal
from pet.domain.models import MemberRole, Membership, Organization
from pet.domain.uow import UnitOfWork
from pet.domain.value_objects import Name as NameVO
from pet.domain.value_objects import PublicId

logger = get_logger(__name__)


@dataclass(frozen=True)
class CreateOrganizationCmdIn:
    name: str
    principal: Principal


async def create_organization_cmd(
    uow: UnitOfWork,
    cmd: CreateOrganizationCmdIn,
    uuid_gen: Callable[[], UUID] = uuid4,
) -> PublicId:
    org_public_id = PublicId.create(uuid_gen())
    logger.debug(
        "organization_create_started",
        organization_name_length=len(cmd.name),
        organization_public_id=org_public_id.value,
    )

    user = await uow.users.get_by_auth_identity(
        issuer=cmd.principal.issuer,
        subject=cmd.principal.subject,
    )
    if user is None:
        raise not_found("User not found")

    org = Organization.create(
        public_id=org_public_id,
        name=NameVO.create(cmd.name),
    )

    membership = Membership.create(
        public_id=PublicId.create(uuid_gen()),
        org_public_id=org.public_id,
        user_public_id=user.public_id,
        role=MemberRole.owner,
    )

    await uow.orgs.create(org)
    await uow.memberships.create(membership)

    logger.debug(
        "organization_create_staged",
        organization_public_id=org_public_id.value,
    )

    return org_public_id
