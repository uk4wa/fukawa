from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from pet.domain.models import Organization as OrgDomain
from pet.domain.models import User as UserDomain
from pet.domain.value_objects import PublicId
from pet.infra.sqla.db.exc import determine_exc
from pet.infra.sqla.db.models import Organization as OrgORM
from pet.infra.sqla.db.models import User as UserORM

DB_OPERATION_ERRORS = (SQLAlchemyError, OSError)


class Repo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


class SQLAlchemyOrganizationsRepo(Repo):
    async def create(self, org: OrgDomain) -> None:
        orm = SQLAlchemyOrganizationsRepo._to_orm(org)
        self._session.add(orm)

    @staticmethod
    def _to_orm(domain: OrgDomain) -> OrgORM:
        return OrgORM(
            public_id=domain.public_id.value,
            name=domain.name.value,
        )


class SQLAlchemyUsersRepo(Repo):
    async def create(self, user: UserDomain) -> None:
        self._session.add(self._to_orm(user))

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

    async def upsert(self, user: UserDomain) -> UserDomain:
        stmt = (
            insert(UserORM)
            .values(
                public_id=user.public_id.value,
                first_name=user.first_name,
                last_name=user.last_name,
                username=user.username,
                email=user.email,
                auth_issuer=user.auth_issuer,
                auth_subject=user.auth_subject,
                last_login_at=user.last_login_at,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            .on_conflict_do_update(
                constraint="uq_users_auth_subject_auth_issuer",
                set_={
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "last_login_at": user.last_login_at,
                    "updated_at": user.updated_at,
                },
            )
            .returning(UserORM)
        )

        try:
            result = await self._session.execute(stmt)
        except DB_OPERATION_ERRORS as e:
            raise determine_exc(e) from e

        orm = result.scalar_one()
        return self._to_domain(orm)

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

    @staticmethod
    def _to_orm(domain: UserDomain) -> UserORM:
        return UserORM(
            public_id=domain.public_id.value,
            first_name=domain.first_name,
            last_name=domain.last_name,
            username=domain.username,
            email=domain.email,
            auth_issuer=domain.auth_issuer,
            auth_subject=domain.auth_subject,
            last_login_at=domain.last_login_at,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )
