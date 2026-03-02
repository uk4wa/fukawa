# import pytest


# class AppError(Exception):
#     message: str

#     def __init__(self, message: str) -> None:
#         super().__init__(message)
#         self.message = message


# def check_num(x: int):
#     if x > 5 and x < 10:
#         raise AppError(message="x between 4 and 10")


# # @pytest.mark.skipif(5 == 5, reason="by")
# @pytest.mark.parametrize("x", [6, 7, 8, 9], ids=lambda v: f"error value {v}")
# def test_error(x: int, fixture: str):
#     with pytest.raises(AppError, match="x between 4 and 10"):
#         check_num(x)


#
#
#
#
# @pytest.mark.parametrize("val", [True, 5 > 3, isinstance("str", str)])
# def test_passed(val):
#     assert val


# @pytest.mark.parametrize("s", [False, 5 < 3])
# def test_failure(s):
#     assert not s


# @pytest.mark.parametrize("s", ["s"])
# def test_failure_2(s):
#     assert s == s
from pytest_mock import MockerFixture
from unittest.mock import Mock
import pytest

from pet.infra.transaction_executor import TransactionExecutor


def test_1(mocker: MockerFixture) -> None:
    mock = mocker.MagicMock()
    mock.side_effect = Exception("err")
    # mock.execute.side_effect = mocker.MagicMock(side_effect=Exception("errMock"))
    mock.execute.return_value = "9000"

    # with pytest.raises(Exception, match="errMock"):
    #     result = mock.execute(12, q="782")
    result = mock.execute(12, q="782")

    assert result == "9000"
    mock.assert_not_called()
    mock.execute.assert_called_once_with(12, q="782")


@pytest.mark.asyncio
async def test_2(uow_factory: Mock, mocker: MockerFixture) -> None:
    mock = mocker.patch.object(
        TransactionExecutor, "run", return_value="hello", autospec=True
    )
    executor = TransactionExecutor(uow_factory)
    handler = mocker.AsyncMock(return_value="ass")

    result = await executor.run(handler)

    assert result == "hello"
    mock.assert_awaited_once_with(executor, handler)


def test_3_spy(mocker: MockerFixture) -> None:
    class AnyC:
        def method(self, *args) -> str:
            return str("".join(args))

    spy = mocker.spy(AnyC, "method")
    anyc = AnyC()

    result = anyc.method("[]l3212  ", "asd", "asda")
    spy.assert_called_once_with(anyc, "[]l3212  ", "asd", "asda")
    assert spy.spy_return == result


def test_4_calls(mocker: MockerFixture) -> None:
    from unittest.mock import call

    class Executor:
        def do(self, i: int) -> None:
            print(i + 2)

    def cicle(args: list[int], obj: Executor) -> None:
        for i in args:
            obj.do(i=i)

    executor = Executor()
    mock = mocker.patch.object(executor, "do", autospec=True)

    calls = [
        call(i=1),
        call(i=2),
        call(i=3),
    ]

    cicle([1, 2, 3], executor)

    mock.assert_has_calls(calls, any_order=False)
