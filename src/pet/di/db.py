from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from pet.domain.uow import UnitOfWork
from pet.infra.sqla.db.repos import SQLAlchemyOrganizationsRepo
from pet.infra.sqla.uow import SQLAlchemyUnitOfWork
from pet.infra.transaction_executor import TransactionExecutor


def get_uow(r: Request) -> UnitOfWork:
    sf = r.app.state.session_factory
    return SQLAlchemyUnitOfWork(
        session_factory=sf,
        orgs_repo_factory=SQLAlchemyOrganizationsRepo,
    )


def get_uow_factory(r: Request) -> Callable[[], UnitOfWork]:
    sf = r.app.state.session_factory

    def factory() -> UnitOfWork:
        return SQLAlchemyUnitOfWork(
            session_factory=sf,
            orgs_repo_factory=SQLAlchemyOrganizationsRepo,
        )

    return factory


def get_executor(
    uow_factory: Annotated[Callable[[], UnitOfWork], Depends(get_uow_factory)],
) -> TransactionExecutor:
    return TransactionExecutor(uow_factory=uow_factory)
