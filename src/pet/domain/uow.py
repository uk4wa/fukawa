from typing import Protocol, Self, Type, Optional
from types import TracebackType
from pet.domain.repos import OrganizationsRepo


class UnitOfWork(Protocol):

    @property
    def orgs(self) -> OrganizationsRepo: ...

    async def __aenter__(self) -> Self: ...
    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None: ...

    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
