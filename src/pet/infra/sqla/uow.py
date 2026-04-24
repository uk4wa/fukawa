from collections.abc import Callable
from types import TracebackType
from typing import Self
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pet.config.logging import get_logger
from pet.domain.repos import OrganizationsRepo
from pet.infra.sqla.db.exc import UoWNotInitializedError, determine_exc

type OrganizationRepoFactory = Callable[[AsyncSession], OrganizationsRepo]
type AsyncSessionFactory = async_sessionmaker[AsyncSession]

logger = get_logger(__name__)


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

        self._uow_id: str = uuid4().hex

    async def __aenter__(self) -> Self:
        session = self._sf()
        try:
            self._session = session
            self._orgs = self._orgs_repo_factory(self._session)

            logger.debug(
                "uow_started",
                uow_id=self._uow_id,
            )

            return self

        except Exception:
            await session.close()

            self._session = None
            self._orgs = None

            logger.exception(
                "uow_start_failed",
                uow_id=self._uow_id,
            )

            raise

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._session is None:
            raise UoWNotInitializedError("session")

        try:
            if exc is not None:
                await self._session.rollback()

                logger.debug(
                    "uow_rolled_back",
                    uow_id=self._uow_id,
                    reason="context_exception",
                    exc_type=type(exc).__name__,
                )

        finally:
            await self.session.close()

            logger.debug(
                "uow_session_closed",
                uow_id=self._uow_id,
            )

            self._session = None
            self._orgs = None

    async def commit(self) -> None:
        try:
            await self.session.commit()

            logger.debug(
                "uow_committed",
                uow_id=self._uow_id,
            )

        except SQLAlchemyError as e:
            await self.session.rollback()

            db_error = determine_exc(e=e)

            logger.debug(
                "uow_commit_failed",
                uow_id=self._uow_id,
                db_error_kind=db_error.kind.value,
            )

            raise db_error from e

    async def rollback(self) -> None:
        try:
            await self.session.rollback()
            logger.debug(
                "uow_rolled_back",
                uow_id=self._uow_id,
                reason="manual",
            )
        except SQLAlchemyError as e:
            logger.exception(
                "uow_rollback_failed",
                uow_id=self._uow_id,
            )
            raise determine_exc(e) from e

    async def flush(self) -> None:
        try:
            await self.session.flush()
        except SQLAlchemyError as e:
            await self.session.rollback()

            db_error = determine_exc(e=e)

            logger.debug(
                "uow_flush_failed",
                uow_id=self._uow_id,
                db_error_kind=db_error.kind.value,
            )

            raise db_error from e

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
