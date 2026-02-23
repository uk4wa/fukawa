from typing import Protocol, Self, Type, Optional, Callable, Concatenate, Awaitable
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
    async def flush(self) -> None: ...
    async def refresh(self, obj: object, attrs: list[str] | None = None) -> None: ...


class TransactionExecutor(Protocol):
    _uow_factory: Callable[[], UnitOfWork]

    async def run[T, **P](
        self,
        handler: Callable[Concatenate[UnitOfWork, P], Awaitable[T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T: ...
