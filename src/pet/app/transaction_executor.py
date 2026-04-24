import time
from collections.abc import Awaitable, Callable
from typing import Concatenate

import structlog

from pet.app.error_mappers import translate_domain_validation_error
from pet.config.logging import get_logger
from pet.domain.exc import ValidationError
from pet.domain.uow import UnitOfWork
from pet.infra.sqla.db.exc import PersistenceError, translate_db_error

logger = get_logger(__name__)


def _handler_name[T, **P](handler: Callable[Concatenate[UnitOfWork, P], Awaitable[T]]) -> str:
    return getattr(handler, "__name__", handler.__class__.__name__)


def _duration_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


class TransactionExecutor:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def run[T, **P](
        self,
        handler: Callable[Concatenate[UnitOfWork, P], Awaitable[T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        started_at = time.perf_counter()
        handler_name = _handler_name(handler)
        logger.debug("transaction_started", use_case_handler=handler_name)

        structlog.contextvars.bind_contextvars(use_case_handler=handler_name)

        async with self._uow_factory() as uow:
            try:
                result = await handler(uow, *args, **kwargs)

                await uow.commit()

                logger.info(
                    "transaction_committed",
                    use_case_handler=handler_name,
                    duration_ms=_duration_ms(started_at),
                )

                return result
            except PersistenceError as e:
                logger.warning(
                    "transaction_db_error",
                    use_case_handler=handler_name,
                    duration_ms=_duration_ms(started_at),
                    persistence_error_kind=getattr(e, "kind", None),
                    sqlstate=getattr(e, "sqlstate", None),
                    constraint_name=getattr(e, "constraint_name", None),
                    retryable=getattr(e, "retryable", None),
                )
                raise translate_db_error(e) from e
            except ValidationError as e:
                logger.warning(
                    "transaction_validation_failed",
                    use_case_handler=handler_name,
                    duration_ms=_duration_ms(started_at),
                    validation_cause=e.cause,
                )
                raise translate_domain_validation_error(e) from e
            except Exception:
                logger.exception(
                    "transaction_failed",
                    use_case_handler=handler_name,
                    duration_ms=_duration_ms(started_at),
                )
                raise
