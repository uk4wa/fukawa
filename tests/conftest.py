import pytest
from unittest.mock import AsyncMock, Mock
from pytest_mock import MockerFixture
from pet.infra.transaction_executor import TransactionExecutor

@pytest.fixture
def uow_mock(mocker: MockerFixture) -> AsyncMock:
    uow = mocker.MagicMock()
    uow.commit = mocker.AsyncMock()
    uow.__aenter__ = mocker.AsyncMock(return_value=uow)
    uow.__aexit__ = mocker.AsyncMock(return_value=False)
    return uow


@pytest.fixture
def uow_factory(uow_mock: AsyncMock, mocker: MockerFixture) -> Mock:
    return mocker.Mock(return_value=uow_mock)


@pytest.fixture
def executor(uow_factory: Mock) -> TransactionExecutor:
    return TransactionExecutor(uow_factory=uow_factory)
