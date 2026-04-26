from dataclasses import dataclass

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from pet.infra.sqla.db.exc import PersistenceError, PersistenceErrorKind, UoWNotInitializedError
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


@pytest.mark.asyncio
async def test_uow_refresh_raises_translated_db_error(mocker: MockerFixture) -> None:
    session_mock = mocker.AsyncMock()
    session_factory_mock = mocker.Mock(return_value=session_mock)
    orgs_repo_factory_mock = mocker.Mock()

    uow = SQLAlchemyUnitOfWork(session_factory_mock, orgs_repo_factory_mock)

    session_mock.refresh.side_effect = SQLAlchemyError("refresh failed")

    translated_error = RuntimeError("translated")
    determine_exc_mock = mocker.patch(
        "pet.infra.sqla.uow.determine_exc",
        return_value=translated_error,
        autospec=True,
    )

    async with uow:
        with pytest.raises(RuntimeError, match="translated") as exc_info:
            await uow.refresh(object(), attrs=["name"])

    assert exc_info.value is translated_error
    session_mock.refresh.assert_awaited_once()
    determine_exc_mock.assert_called_once()


@pytest.mark.asyncio
async def test_flush_error(mocker: MockerFixture) -> None:
    session = mocker.AsyncMock()
    error_mock = SQLAlchemyError("flush failed")
    session.flush = mocker.AsyncMock(side_effect=error_mock)

    uow = SQLAlchemyUnitOfWork(
        session_factory=mocker.Mock(return_value=session),
        orgs_repo_factory=mocker.Mock(),
    )
    uow._rollback_after_failure = mocker.AsyncMock()
    translated_error = PersistenceError(kind=PersistenceErrorKind.UNKNOWN)

    deteremine_error_mock = mocker.patch(
        "pet.infra.sqla.uow.determine_exc",
        return_value=translated_error,
        autospec=True,
    )

    # rollback_after_failure_mock = mocker.patch(
    #     "pet.infra.sqla.uow.SQLAlchemyUnitOfWork._rollback_after_failure",
    #     new_callable=mocker.AsyncMock,
    # )

    async with uow:
        with pytest.raises(PersistenceError) as exc_info:
            await uow.flush()

    assert exc_info.value is translated_error
    session.flush.assert_awaited_once()
    deteremine_error_mock.assert_called_once_with(e=error_mock)
    uow._rollback_after_failure.assert_awaited_once_with(reason="flush_failed")


@pytest.mark.asyncio
async def test_rollback_after_failure_raise_error(mocker: MockerFixture) -> None:
    session_mock = mocker.AsyncMock()
    session_mock.rollback.side_effect = SQLAlchemyError("rollback error")
    session_factory_mock = mocker.Mock(return_value=session_mock)

    uow = SQLAlchemyUnitOfWork(
        session_factory=session_factory_mock,
        orgs_repo_factory=mocker.Mock(),
    )

    logger_mock = mocker.patch(
        "pet.infra.sqla.uow.logger.exception",
        new_callable=mocker.Mock,
    )

    async with uow:
        await uow._rollback_after_failure(reason="rollback failed")

    logger_mock.assert_called_once()
