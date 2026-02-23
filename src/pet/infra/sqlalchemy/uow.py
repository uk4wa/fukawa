from types import TracebackType
from typing import Self, Optional, Type
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from pet.domain.repos import OrganizationsRepo
from pet.infra.sqlalchemy.db.exc import determine_exc, UoWNotInitializedError

# from pet.domain.exc import Conflict, DBError, DBErrorKind
from sqlalchemy.exc import SQLAlchemyError


OrganizationRepoFactory = Callable[[AsyncSession], OrganizationsRepo]
AsyncSessionFactory = async_sessionmaker[AsyncSession]


class SQLAlchemyUnitOfWork:
    def __init__(
        self,
        session_factory: AsyncSessionFactory,
        orgs_repo_factory: OrganizationRepoFactory,
    ) -> None:
        self._sf: AsyncSessionFactory = session_factory
        self._orgs_repo_factory: OrganizationRepoFactory = orgs_repo_factory

        self._session: AsyncSession | None = None
        self._orgs: OrganizationsRepo | None = None

    async def __aenter__(self) -> Self:
        session = self._sf()
        try:
            self._session = session
            self._orgs = self._orgs_repo_factory(self._session)
            return self
        except Exception:
            await session.close()
            self._session = None
            self._orgs = None
            raise

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        if self._session is None:
            raise UoWNotInitializedError("session")

        try:
            if exc is not None:
                await self._session.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise determine_exc(e=e)

    async def rollback(self) -> None:
        await self.session.rollback()

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, obj: object, attrs: list[str] | None = None) -> None:
        await self.session.refresh(obj, attribute_names=attrs)

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise UoWNotInitializedError("session")
        return self._session

    @property
    def orgs(self) -> OrganizationsRepo:
        if self._orgs is None:
            raise UoWNotInitializedError("orgs")
        return self._orgs
