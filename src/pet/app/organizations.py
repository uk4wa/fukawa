from dataclasses import dataclass

from pet.domain.uow import UnitOfWork
from pet.domain.models import Organization


@dataclass(frozen=True)
class CreateOrganizationCmdIn:
    name: str


async def create_organization_cmd(
    cmd: CreateOrganizationCmdIn,
    uow: UnitOfWork,
):
    domain_org = Organization.new(name=cmd.name)
    async with uow:
        uow.orgs.create(domain_org)
        await uow.commit()
