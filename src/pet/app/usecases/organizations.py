from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

import structlog

from pet.config.logging import get_logger
from pet.domain.models import Organization
from pet.domain.uow import UnitOfWork
from pet.domain.value_objects import Name as NameVO
from pet.domain.value_objects import PublicId as PublicIdVO

logger = get_logger(__name__)


@dataclass(frozen=True)
class CreateOrganizationCmdIn:
    name: str


@dataclass
class PublicId:
    val: UUID


async def create_organization_cmd(
    uow: UnitOfWork,
    cmd: CreateOrganizationCmdIn,
    uuid_gen: Callable[[], UUID] = uuid4,
) -> PublicId:
    structlog.contextvars.bind_contextvars(
        use_case="create_organization",
        organization_name_length=len(cmd.name),
    )
    logger.info("organization_create_started")

    public_id = uuid_gen()
    structlog.contextvars.bind_contextvars(organization_public_id=str(public_id))
    domain_org = Organization.create(
        public_id=PublicIdVO.create(public_id),
        name=NameVO.create(cmd.name),
    )
    uow.orgs.create(domain_org)
    logger.info("organization_create_staged")

    return PublicId(public_id)
