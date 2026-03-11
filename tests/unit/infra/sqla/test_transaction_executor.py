from unittest.mock import ANY, AsyncMock, Mock

import pytest
from pytest_mock import MockerFixture

from pet.infra.transaction_executor import TransactionExecutor


@pytest.mark.asyncio
async def test_transaction_executor_passed(
    uow_mock: AsyncMock,
    uow_factory: Mock,
    mocker: MockerFixture,
    executor: TransactionExecutor,
) -> None:
    handler = mocker.AsyncMock(return_value="ok")

    result = await executor.run(handler, 123, q="123str")

    assert result == "ok"
    uow_factory.assert_called_once_with()
    uow_mock.__aenter__.assert_awaited_once_with()
    handler.assert_awaited_once_with(uow_mock, 123, q="123str")
    uow_mock.commit.assert_awaited_once()
    uow_mock.__aexit__.assert_awaited_once_with(None, None, None)


@pytest.mark.asyncio
async def test_transaction_executor_failed_raised_db_exception(
    uow_mock: AsyncMock,
    uow_factory: Mock,
    mocker: MockerFixture,
    executor: TransactionExecutor,
) -> None:
    class FakeDBError(Exception):
        pass

    class TranslatedError(Exception):
        pass

    mocker.patch("pet.infra.transaction_executor.DBError", FakeDBError)
    translated_exc = TranslatedError("translated_exc")
    translated_db_error = mocker.patch(
        "pet.infra.transaction_executor.translate_db_error",
        return_value=translated_exc,
        autospec=True,
    )
    fake_db_error = FakeDBError("db_exc")
    handler = mocker.AsyncMock(side_effect=fake_db_error, spec=True)

    with pytest.raises(TranslatedError) as exc_info:
        await executor.run(handler, 2321, q="str")

    assert exc_info.value is translated_db_error.return_value
    uow_factory.assert_called_once_with()
    translated_db_error.assert_called_once_with(fake_db_error)
    handler.assert_awaited_once_with(uow_mock, 2321, q="str")
    uow_mock.commit.assert_not_awaited()

    uow_mock.__aexit__.assert_awaited_once_with(TranslatedError, translated_exc, ANY)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception",
    [Exception("err"), RuntimeError("err")],
)
async def test_transaction_executor_failed_raise_any_exception(
    exception: Exception,
    uow_mock: AsyncMock,
    uow_factory: Mock,
    mocker: MockerFixture,
    executor: TransactionExecutor,
) -> None:
    handler = mocker.AsyncMock(side_effect=exception, spec=True)
    translate_db_error = mocker.patch(
        "pet.infra.transaction_executor.translate_db_error",
        autospec=True,
    )

    with pytest.raises(type(exception), match="err") as exc_info:
        await executor.run(handler, 1)

    assert exc_info.value is exception
    uow_factory.assert_called_once_with()
    handler.assert_awaited_once_with(uow_mock, 1)
    uow_mock.commit.assert_not_awaited()
    translate_db_error.assert_not_called()

    uow_mock.__aenter__.assert_awaited_once()
    uow_mock.__aexit__.assert_awaited_once_with(type(exception), exception, ANY)
