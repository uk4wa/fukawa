from sqlalchemy.ext.asyncio import AsyncSession
from pet.domain.models import Organization as Domain
from pet.infra.sqlalchemy.db.models import Organization as ORM


class SQLAlchemyOrganizationsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def create(self, org: Domain) -> None:
        orm = SQLAlchemyOrganizationsRepo._to_orm(org)
        self._session.add(orm)

    @staticmethod
    def _to_orm(domain: Domain) -> ORM:
        return ORM(name=domain.name)
