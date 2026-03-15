from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

import structlog

from pet.domain.models import Organization
from pet.domain.uow import UnitOfWork
from pet.domain.value_objects import Name as NameVO
from pet.domain.value_objects import PublicId as PublicIdVO


@dataclass(frozen=True)
class CreateOrganizationCmdIn:
    name: str


@dataclass
class PublicId:
    val: UUID


logger = structlog.get_logger(__name__)


async def create_organization_cmd(
    uow: UnitOfWork,
    cmd: CreateOrganizationCmdIn,
    uuid_gen: Callable[[], UUID] = uuid4,
) -> PublicId:
    public_id = uuid_gen()
    domain_org = Organization.new(
        public_id=PublicIdVO.new(public_id),
        name=NameVO.create(cmd.name),
    )
    uow.orgs.create(domain_org)

    return PublicId(public_id)
