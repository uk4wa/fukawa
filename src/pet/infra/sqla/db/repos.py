import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from pet.domain.models import Membership as MembershipDomain
from pet.domain.models import Organization as OrgDomain
from pet.domain.models import User as UserDomain
from pet.domain.value_objects import PublicId
from pet.infra.sqla.db.exc import DB_OPERATION_ERRORS, determine_exc
from pet.infra.sqla.db.models import Membership as MembershipORM
from pet.infra.sqla.db.models import Organization as OrgORM
from pet.infra.sqla.db.models import OrgRole
from pet.infra.sqla.db.models import User as UserORM


class Repo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


class SQLAlchemyOrganizationsRepo(Repo):
    async def create(self, org: OrgDomain) -> None:
        self._session.add(
            OrgORM(
                public_id=org.public_id.value,
                name=org.name.value,
            )
        )


class SQLAlchemyMembershipsRepo(Repo):
    async def create(self, membership: MembershipDomain) -> None:
        # Due to a postgresql petition, the post with 3 queries instead of 1
        # stmt = insert(MembershipORM).from_select(
        #     ["public_id", "user_id", "org_id", "user_role"],
        #     select(
        #         sa.literal(membership.public_id.value).label("public_id"),
        #         UserORM.id.label("user_id"),
        #         OrgORM.id.label("org_id"),
        #         sa.literal(OrgRole(membership.role.value)).label("user_role"),
        #     ).where(
        #         UserORM.public_id == membership.user_public_id.value,
        #         OrgORM.public_id == membership.org_public_id.value,
        #     ),
        # )
        # is more readable, and the postgresql query planner
        # ends up doing the same thing.
        user_id_subq = (
            select(UserORM.id)
            .where(UserORM.public_id == membership.user_public_id.value)
            .scalar_subquery()
        )
        org_id_subq = (
            select(OrgORM.id)
            .where(OrgORM.public_id == membership.org_public_id.value)
            .scalar_subquery()
        )

        stmt = insert(MembershipORM).values(
            public_id=membership.public_id.value,
            user_id=user_id_subq,
            org_id=org_id_subq,
            user_role=OrgRole(membership.role.value),
        )

        try:
            await self._session.execute(stmt)
        except DB_OPERATION_ERRORS as e:
            raise determine_exc(e) from e


class SQLAlchemyUsersRepo(Repo):
    async def get_by_auth_identity(self, issuer: str, subject: str) -> UserDomain | None:
        stmt = select(UserORM).where(
            UserORM.auth_issuer == issuer,
            UserORM.auth_subject == subject,
        )

        try:
            result = await self._session.execute(stmt)
        except DB_OPERATION_ERRORS as e:
            raise determine_exc(e) from e

        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def upsert(self, user: UserDomain) -> tuple[UserDomain, bool]:
        insert_stmt = insert(UserORM).values(
            public_id=user.public_id.value,
            auth_issuer=user.auth_issuer,
            auth_subject=user.auth_subject,
            email=user.email,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            last_login_at=user.last_login_at,
            updated_at=user.updated_at,
            created_at=user.created_at,
        )

        stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_users_auth_subject_auth_issuer",
            set_={
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "last_login_at": user.last_login_at,
                "updated_at": user.updated_at,
            },
        ).returning(
            UserORM,
            sa.literal_column("(xmax = 0)", sa.Boolean).label("inserted"),
        )

        try:
            result = await self._session.execute(stmt)
        except DB_OPERATION_ERRORS as e:
            raise determine_exc(e) from e

        row = result.one()
        return self._to_domain(row[0]), row.inserted

    @staticmethod
    def _to_domain(orm: UserORM) -> UserDomain:
        return UserDomain(
            public_id=PublicId(value=orm.public_id),
            first_name=orm.first_name,
            last_name=orm.last_name,
            username=orm.username,
            email=orm.email,
            auth_issuer=orm.auth_issuer,
            auth_subject=orm.auth_subject,
            last_login_at=orm.last_login_at,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )
