from dataclasses import dataclass

from pet.domain.uow import UnitOfWork
from pet.domain.models import Organization
from typing import Callable
from uuid import UUID, uuid4


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
    public_id = uuid_gen()
    domain_org = Organization.new(public_id=public_id, name=cmd.name)
    uow.orgs.create(domain_org)

    return PublicId(public_id)
