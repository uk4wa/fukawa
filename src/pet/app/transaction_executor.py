from collections.abc import Awaitable, Callable
from typing import Concatenate

from pet.app.exc import translate_db_error, translate_domain_validation_error
from pet.domain.exc import DBError, ValidationError
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
            except ValidationError as e:
                raise translate_domain_validation_error(e) from e
