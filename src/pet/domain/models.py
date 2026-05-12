import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Self

from pet.domain.value_objects import Name, PublicId


class MemberRole(enum.StrEnum):
    owner = "owner"
    admin = "admin"
    member = "member"


@dataclass(frozen=True, slots=True)
class Organization:
    public_id: PublicId
    name: Name = field(compare=False)

    @classmethod
    def create(
        cls,
        public_id: PublicId,
        name: Name,
    ) -> Self:
        return cls(
            public_id=public_id,
            name=name,
        )


@dataclass(frozen=True, slots=True)
class Membership:
    public_id: PublicId
    org_public_id: PublicId
    user_public_id: PublicId
    role: MemberRole

    @classmethod
    def create(
        cls,
        public_id: PublicId,
        org_public_id: PublicId,
        user_public_id: PublicId,
        role: MemberRole,
    ) -> Self:
        return cls(
            public_id=public_id,
            org_public_id=org_public_id,
            user_public_id=user_public_id,
            role=role,
        )


@dataclass(frozen=True, slots=True)
class User:
    public_id: PublicId

    email: str

    username: str
    first_name: str | None
    last_name: str | None

    auth_issuer: str
    auth_subject: str

    last_login_at: datetime
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        public_id: PublicId,
        email: str,
        auth_issuer: str,
        auth_subject: str,
        username: str,
        last_login_at: datetime,
        created_at: datetime,
        updated_at: datetime | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> "User":
        return cls(
            public_id=public_id,
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            auth_issuer=auth_issuer,
            auth_subject=auth_subject,
            last_login_at=last_login_at,
            created_at=created_at,
            updated_at=updated_at or created_at,
        )
