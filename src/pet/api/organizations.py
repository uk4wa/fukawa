from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from pet.app.organizations import CreateOrganizationCmdIn, create_organization_cmd
from pet.di.db import get_executor
from pet.domain.uow import TransactionExecutor
from pet.domain.value_objects import ORG_NAME_MAX_LEN, ORG_NAME_MIN_LEN

organizationsAPI = APIRouter(prefix="/orgs")

Executor = Annotated[TransactionExecutor, Depends(get_executor)]


class CreateOrgDtoIn(BaseModel):
    name: str = Field(..., min_length=ORG_NAME_MIN_LEN, max_length=ORG_NAME_MAX_LEN)


class PublicId(BaseModel):
    public_id: UUID


@organizationsAPI.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=PublicId,
)
async def create_organization_v2(
    org: CreateOrgDtoIn,
    executor: Executor,
):
    cmd = CreateOrganizationCmdIn(name=org.name)
    public_id = await executor.run(create_organization_cmd, cmd)
    return PublicId(public_id=public_id.val)
