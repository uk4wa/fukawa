from fastapi import Request
from pet.domain.uow import UnitOfWork
from pet.infra.uow import SQLAlchemyUnitOfWork
from pet.infra.db.repos import SQLAlchemyOrganizationsRepo


def get_uow(r: Request) -> UnitOfWork:
    sf = r.app.state.session_factory
    return SQLAlchemyUnitOfWork(
        session_factory=sf,
        orgs_repo_factory=SQLAlchemyOrganizationsRepo,
    )
