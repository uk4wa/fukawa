from typing import Protocol
from pet.domain.models import Organization


class OrganizationsRepo(Protocol):
    def create(self, org: Organization) -> None: ...
