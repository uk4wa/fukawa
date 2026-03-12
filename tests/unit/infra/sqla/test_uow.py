from dataclasses import dataclass

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

from pet.infra.sqla.db.exc import UoWNotInitializedError
from pet.infra.sqla.uow import SQLAlchemyUnitOfWork


@pytest.mark.asyncio
async def test_uow_aenter_failed(mocker: MockerFixture):
    @dataclass
    class OrgsRepoFactoryException(Exception):
        message: str

    session_mock = mocker.AsyncMock(spec=AsyncSession)
    session_factory_mock = mocker.Mock(return_value=session_mock)
    expected_err = OrgsRepoFactoryException(message="orgs_repos_factory_exception")
    orgs_repo_factory_mock = mocker.Mock(side_effect=expected_err)
    uow = SQLAlchemyUnitOfWork(session_factory_mock, orgs_repo_factory_mock)

    with pytest.raises(OrgsRepoFactoryException) as e:
        async with uow:
            pass

    assert e.value is expected_err

    session_factory_mock.assert_called_once_with()
    orgs_repo_factory_mock.assert_called_once_with(session_mock)
    session_mock.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_uow_get_session(mocker: MockerFixture):

    session_mock = mocker.AsyncMock()
    session_factory_mock = mocker.Mock(return_value=session_mock)
    orgs_repo_factory_mock = mocker.Mock()
    uow = SQLAlchemyUnitOfWork(session_factory_mock, orgs_repo_factory_mock)

    expected_err = UoWNotInitializedError(field="session")

    with pytest.raises(UoWNotInitializedError) as e:
        _ = uow.session

    assert e.value.field == expected_err.field

    orgs_repo_factory_mock.assert_not_called()
    session_factory_mock.assert_not_called()
    session_mock.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_uow_get_orgs(mocker: MockerFixture):

    session_mock = mocker.AsyncMock()
    session_factory_mock = mocker.Mock(return_value=session_mock)
    orgs_repo_factory_mock = mocker.Mock()
    uow = SQLAlchemyUnitOfWork(session_factory_mock, orgs_repo_factory_mock)

    expected_err = UoWNotInitializedError(field="orgs")

    with pytest.raises(UoWNotInitializedError) as e:
        _ = uow.orgs

    assert e.value.field == expected_err.field

    orgs_repo_factory_mock.assert_not_called()
    session_factory_mock.assert_not_called()
    session_mock.close.assert_not_awaited()
