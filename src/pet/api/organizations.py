from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, StrictStr, field_validator

from pet.app.usecases.organizations import CreateOrganizationCmdIn, create_organization_cmd
from pet.di.db import get_executor
from pet.domain.uow import TransactionExecutorProtocol
from pet.domain.value_objects import ORG_NAME_DESCRIPTION, validate_org_name

organizations = APIRouter(prefix="/orgs")

Executor = Annotated[TransactionExecutorProtocol, Depends(get_executor)]


class CreateOrgDtoIn(BaseModel):
    name: StrictStr = Field(
        description=ORG_NAME_DESCRIPTION,
        examples=["Acme", "Strasse"],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_org_name(value)


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
) -> PublicId:
    cmd = CreateOrganizationCmdIn(name=org.name)
    public_id = await executor.run(create_organization_cmd, cmd)
    return PublicId(public_id=public_id.val)
