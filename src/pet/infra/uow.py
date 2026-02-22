from types import TracebackType
from typing import Self, Optional, Type

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from collections.abc import Callable
from pet.domain.repos import OrganizationsRepo

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
            raise Exception("UoW don't init")

        try:
            if exc is not None:
                await self._session.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise Exception("поле session не инициализировано")
        return self._session

    @property
    def orgs(self) -> OrganizationsRepo:
        if self._orgs is None:
            raise Exception("поле orgs не инициализировано")
        return self._orgs
