from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from pet.api.auth import CurrentPrincipal
from pet.app.usecases.users import provision_user_from_claims
from pet.di.db import Executor
from pet.domain.models import User

users = APIRouter(prefix="/users")


class MeOut(BaseModel):
    public_id: UUID
    email: str
    username: str
    first_name: str | None
    last_name: str | None
    last_login_at: datetime


@users.post(
    "/me",
    response_model=User,
    status_code=status.HTTP_200_OK,
)
async def login(
    principal: CurrentPrincipal,
    executor: Executor,
    response: Response,
) -> MeOut:
    provision, created = await executor.run(provision_user_from_claims, principal)

    if created:
        response.status_code = status.HTTP_201_CREATED

    return MeOut(
        public_id=provision.public_id.value,
        email=provision.email,
        username=provision.username,
        first_name=provision.first_name,
        last_name=provision.last_name,
        last_login_at=provision.last_login_at,
    )
