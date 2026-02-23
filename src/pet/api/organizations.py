from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Annotated

from pet.domain.uow import TransactionExecutor
from pet.di.db import get_executor
from pet.app.organizations import CreateOrganizationCmdIn, create_organization_cmd

Executor = Annotated[TransactionExecutor, Depends(get_executor)]

organizationsAPI = APIRouter(prefix="/orgs")


class CreateOrgDtoIn(BaseModel):
    name: str = Field(..., max_length=320)


@organizationsAPI.post("/")
async def create_organization_v2(
    org: CreateOrgDtoIn,
    executor: Executor,
):
    cmd = CreateOrganizationCmdIn(name=org.name)
    await executor.run(create_organization_cmd, cmd)
