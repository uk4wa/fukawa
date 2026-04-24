from collections.abc import Callable
from types import TracebackType
from typing import Final, Self
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pet.config.logging import get_logger
from pet.domain.repos import OrganizationsRepo
from pet.infra.sqla.db.exc import UoWNotInitializedError, determine_exc

type OrganizationRepoFactory = Callable[[AsyncSession], OrganizationsRepo]
type AsyncSessionFactory = async_sessionmaker[AsyncSession]

logger = get_logger(__name__)

DB_OPERATION_ERRORS: Final = (SQLAlchemyError, OSError)


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

        self._rolled_back: bool = False
        self._uow_id: str | None = uuid4().hex

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
            if exc is not None and not self._rolled_back:
                await self._session.rollback()

                logger.debug(
                    "uow_rolled_back",
                    uow_id=self._uow_id,
                    reason="context_exception",
                    exc_type=type(exc).__name__,
                )
        except DB_OPERATION_ERRORS as e:
            raise determine_exc(e) from e
        finally:
            await self.session.close()

            logger.debug(
                "uow_session_closed",
                uow_id=self._uow_id,
            )

            self._session = None
            self._orgs = None
            self._uow_id = None
            self._rolled_back = False

    async def commit(self) -> None:
        try:
            await self.session.commit()

            logger.debug(
                "uow_committed",
                uow_id=self._uow_id,
            )

        except DB_OPERATION_ERRORS as e:
            db_error = determine_exc(e=e)

            await self._rollback_after_failure(reason="commit_failed")

            logger.debug(
                "uow_commit_failed",
                uow_id=self._uow_id,
                db_error_kind=db_error.kind.value,
            )

            raise db_error from e

    async def rollback(self) -> None:
        try:
            await self.session.rollback()
            self._rolled_back = True
            logger.debug(
                "uow_rolled_back",
                uow_id=self._uow_id,
                reason="manual",
            )
        except DB_OPERATION_ERRORS as e:
            logger.exception(
                "uow_rollback_failed",
                uow_id=self._uow_id,
            )
            raise determine_exc(e) from e

    async def _rollback_after_failure(self, *, reason: str) -> None:
        try:
            await self.session.rollback()
            self._rolled_back = True
        except DB_OPERATION_ERRORS:
            logger.exception(
                "uow_rollback_after_failure_failed",
                uow_id=self._uow_id,
                reason=reason,
            )

    async def flush(self) -> None:
        try:
            await self.session.flush()
        except DB_OPERATION_ERRORS as e:
            db_error = determine_exc(e=e)

            await self._rollback_after_failure(reason="flush_failed")

            logger.debug(
                "uow_flush_failed",
                uow_id=self._uow_id,
                db_error_kind=db_error.kind.value,
            )

            raise db_error from e

    async def refresh(self, obj: object, attrs: list[str] | None = None) -> None:
        try:
            await self.session.refresh(obj, attribute_names=attrs)
        except DB_OPERATION_ERRORS as e:
            raise determine_exc(e=e) from e

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
