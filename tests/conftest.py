from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from pet.app.transaction_executor import TransactionExecutor
from pet.domain.uow import UnitOfWork


@pytest.fixture
def uow_mock(mocker: MockerFixture) -> Mock:
    uow = mocker.MagicMock(spec=UnitOfWork)
    uow.commit = mocker.AsyncMock()
    uow.__aenter__ = mocker.AsyncMock(return_value=uow)
    uow.__aexit__ = mocker.AsyncMock(return_value=False)
    return uow


@pytest.fixture
def uow_factory(uow_mock: Mock, mocker: MockerFixture) -> Mock:
    return mocker.Mock(return_value=uow_mock)


@pytest.fixture
def executor(uow_factory: Mock) -> TransactionExecutor:
    return TransactionExecutor(uow_factory=uow_factory)
