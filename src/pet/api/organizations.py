from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, StrictStr

from pet.app.organizations import CreateOrganizationCmdIn, create_organization_cmd
from pet.di.db import get_executor
from pet.domain.uow import TransactionExecutor

organizations = APIRouter(prefix="/orgs")

Executor = Annotated[TransactionExecutor, Depends(get_executor)]


class CreateOrgDtoIn(BaseModel):
    name: StrictStr


class PublicId(BaseModel):
    public_id: UUID


@organizations.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=PublicId,
)
async def create_organization(
    org: CreateOrgDtoIn,
    executor: Executor,
):
    cmd = CreateOrganizationCmdIn(name=org.name)
    public_id = await executor.run(create_organization_cmd, cmd)
    return PublicId(public_id=public_id.val)
