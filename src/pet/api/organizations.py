from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from pet.domain.uow import UnitOfWork

from pet.di.uow import get_uow
from typing import Annotated
from pet.domain.uow import UnitOfWork

UoW = Annotated[UnitOfWork, Depends(get_uow)]

organizationsAPI = APIRouter(prefix="/orgs")


class CreateOrgDtoIn(BaseModel):
    name: str = Field(..., max_length=320)


from pet.app.organizations import CreateOrganizationCmdIn, create_organization_cmd


@organizationsAPI.post("/")
async def create_organization(org: CreateOrgDtoIn, uow: UoW):
    cmd = CreateOrganizationCmdIn(name=org.name)
    await create_organization_cmd(cmd=cmd, uow=uow)
