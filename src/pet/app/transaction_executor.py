from collections.abc import Awaitable, Callable
from typing import Concatenate

from pet.domain.exc import DBError, translate_db_error
from pet.domain.uow import UnitOfWork


class TransactionExecutor:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def run[T, **P](
        self,
        handler: Callable[Concatenate[UnitOfWork, P], Awaitable[T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        async with self._uow_factory() as uow:
            try:
                result = await handler(uow, *args, **kwargs)
                await uow.commit()
                return result
            except DBError as e:
                raise translate_db_error(e) from e
