from typing import Protocol

from pet.domain.models import Membership, Organization, User


class OrganizationsRepo(Protocol):
    async def create(self, org: Organization) -> None: ...


class MembershipsRepo(Protocol):
    async def create(self, membership: Membership) -> None: ...


class UsersRepo(Protocol):
    async def upsert(self, user: User) -> tuple[User, bool]: ...
    async def get_by_auth_identity(self, issuer: str, subject: str) -> User | None: ...
