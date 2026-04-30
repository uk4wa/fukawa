from typing import Any
from unittest.mock import ANY, AsyncMock, Mock

import pytest
from pytest_mock import MockerFixture

from pet.app.transaction_executor import TransactionExecutor
from pet.domain.exc import ValidationError


@pytest.mark.asyncio
async def test_transaction_executor_passed(
    uow_mock: AsyncMock,
    uow_factory_mock: Mock,
    mocker: MockerFixture,
    executor: TransactionExecutor,
) -> None:
    handler = mocker.AsyncMock(return_value="ok")
    info_log = mocker.patch("pet.app.transaction_executor.logger.info")
    debug_log = mocker.patch("pet.app.transaction_executor.logger.debug")

    result = await executor.run(handler, 123, q="123str")

    assert result == "ok"
    uow_factory_mock.assert_called_once_with()
    uow_mock.__aenter__.assert_awaited_once_with()
    handler.assert_awaited_once_with(uow_mock, 123, q="123str")
    uow_mock.commit.assert_awaited_once()
    uow_mock.__aexit__.assert_awaited_once_with(None, None, None)
    debug_log.assert_called_once()
    info_log.assert_called_once()
    assert info_log.call_args.args == ("transaction_committed",)
    assert info_log.call_args.kwargs["use_case_handler"] == handler.__name__


@pytest.mark.asyncio
async def test_transaction_executor_failed_raised_db_exception(
    uow_mock: AsyncMock,
    uow_factory_mock: Mock,
    mocker: MockerFixture,
    executor: TransactionExecutor,
) -> None:
    class FakeDBError(Exception):
        kind: Any
        sqlstate: Any = None
        constraint_name: Any = None
        retryable: Any = None

    class TranslatedError(Exception):
        pass

    mocker.patch("pet.app.transaction_executor.PersistenceError", FakeDBError)
    translated_exc = TranslatedError("translated_exc")
    translated_db_error = mocker.patch(
        "pet.app.transaction_executor.translate_db_error",
        return_value=translated_exc,
        autospec=True,
    )
    warning_log = mocker.patch("pet.app.transaction_executor.logger.warning")
    fake_db_error = FakeDBError("db_exc")
    fake_db_error.kind = mocker.Mock(value="fake_kind")
    handler = mocker.AsyncMock(side_effect=fake_db_error, spec=True)

    with pytest.raises(TranslatedError) as exc_info:
        await executor.run(handler, 2321, q="str")

    assert exc_info.value is translated_db_error.return_value
    uow_factory_mock.assert_called_once_with()
    translated_db_error.assert_called_once_with(fake_db_error)
    handler.assert_awaited_once_with(uow_mock, 2321, q="str")
    uow_mock.commit.assert_not_awaited()

    uow_mock.__aexit__.assert_awaited_once_with(TranslatedError, translated_exc, ANY)
    warning_log.assert_called_once()
    assert warning_log.call_args.args == ("transaction_db_error",)


@pytest.mark.asyncio
async def test_transaction_executor_failed_raises_translated_validation_exception(
    uow_mock: AsyncMock,
    uow_factory_mock: Mock,
    mocker: MockerFixture,
    executor: TransactionExecutor,
) -> None:
    class TranslatedError(Exception):
        pass

    translated_exc = TranslatedError("translated_validation")
    translate_validation_error = mocker.patch(
        "pet.app.transaction_executor.translate_domain_validation_error",
        return_value=translated_exc,
        autospec=True,
    )
    warning_log = mocker.patch("pet.app.transaction_executor.logger.warning")
    validation_error = ValidationError("invalid organization name", cause="name")
    handler = mocker.AsyncMock(side_effect=validation_error, spec=True)

    with pytest.raises(TranslatedError) as exc_info:
        await executor.run(handler, 1)

    assert exc_info.value is translated_exc
    uow_factory_mock.assert_called_once_with()
    handler.assert_awaited_once_with(uow_mock, 1)
    uow_mock.commit.assert_not_awaited()
    translate_validation_error.assert_called_once_with(validation_error)
    uow_mock.__aexit__.assert_awaited_once_with(TranslatedError, translated_exc, ANY)
    warning_log.assert_called_once()
    assert warning_log.call_args.args == ("transaction_validation_failed",)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception",
    [Exception("err"), RuntimeError("err")],
)
async def test_transaction_executor_failed_raise_any_exception(
    exception: Exception,
    uow_mock: AsyncMock,
    uow_factory_mock: Mock,
    mocker: MockerFixture,
    executor: TransactionExecutor,
) -> None:
    handler = mocker.AsyncMock(side_effect=exception, spec=True)
    translate_db_error = mocker.patch(
        "pet.app.transaction_executor.translate_db_error",
        autospec=True,
    )
    translate_validation_error = mocker.patch(
        "pet.app.transaction_executor.translate_domain_validation_error",
        autospec=True,
    )
    exception_log = mocker.patch("pet.app.transaction_executor.logger.exception")

    with pytest.raises(type(exception), match="err") as exc_info:
        await executor.run(handler, 1)

    assert exc_info.value is exception
    uow_factory_mock.assert_called_once_with()
    handler.assert_awaited_once_with(uow_mock, 1)
    uow_mock.commit.assert_not_awaited()
    translate_db_error.assert_not_called()
    translate_validation_error.assert_not_called()

    uow_mock.__aenter__.assert_awaited_once()
    uow_mock.__aexit__.assert_awaited_once_with(type(exception), exception, ANY)
    exception_log.assert_called_once()
    assert exception_log.call_args.args == ("transaction_failed",)
