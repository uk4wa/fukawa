import pytest
from pytest_mock import MockerFixture
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from pet.domain.exc import Conflict, DBError, DBErrorKind, InternalError, translate_db_error
from pet.infra.sqla.db.exc import determine_exc, pg_sqlstate_from_integrity

# determine_exc tests


@pytest.mark.parametrize(
    ("sqlstate", "expected_kind"),
    [
        ("23505", DBErrorKind.UNIQUE),
        ("23503", DBErrorKind.FK),
        ("23502", DBErrorKind.NOT_NULL),
        ("23514", DBErrorKind.CHECK),
        ("99999", DBErrorKind.UNKNOWN),
        (None, DBErrorKind.UNKNOWN),
    ],
)
def test_determine_exc_maps_integrity_sqlstate(
    mocker: MockerFixture,
    sqlstate: str | None,
    expected_kind: DBErrorKind,
):
    error = IntegrityError(
        statement="statement", params={"name": "acme"}, orig=Exception()
    )

    pg_sqlstate_mock = mocker.patch(
        "pet.infra.sqla.db.exc.pg_sqlstate_from_integrity",
        return_value=sqlstate,
    )

    result = determine_exc(error)

    assert result.kind == expected_kind
    assert result.title == "db_integrity"
    assert result.retryable == False
    assert result.sqlstate == sqlstate
    assert result.cause is error

    pg_sqlstate_mock.assert_called_once_with(error)


def test_determine_exc_maps_operational_error(mocker: MockerFixture):
    error = OperationalError(
        statement="statement", params={"name": "acme"}, orig=Exception()
    )

    result = determine_exc(error)

    assert result.kind == DBErrorKind.OPERATIONAL
    assert result.title == "db_unvailable"
    assert result.retryable == True
    assert result.sqlstate is None
    assert result.cause is error


def test_determine_exc_maps_unknown_sqla_error(mocker: MockerFixture):
    error = SQLAlchemyError("unknown")

    result = determine_exc(error)

    assert isinstance(result, DBError)
    assert result.kind == DBErrorKind.UNKNOWN
    assert result.title == "db_error"
    assert result.retryable is False
    assert result.cause is error


# pg_sqlstate_from_integrity tests


def test_pg_sqlstate_from_integrity_reads_sqlstate_first(mocker: MockerFixture):
    error = mocker.Mock()
    error.orig = mocker.Mock(sqlstate="23505", pgcode="99999")

    result = pg_sqlstate_from_integrity(err=error)

    assert result == "23505"


def test_pg_sqlstate_from_integrity_falls_back_to_pgcode(mocker: MockerFixture) -> None:
    error = mocker.Mock()
    error.orig = mocker.Mock(sqlstate=None, pgcode="23503")

    result = pg_sqlstate_from_integrity(error)

    assert result == "23503"


def test_translate_db_error_returns_conflict_for_unique(mocker: MockerFixture):
    error = DBError(
        kind=DBErrorKind.UNIQUE,
        title="error title",
        detail="error detail",
    )

    result = translate_db_error(error)

    assert isinstance(result, Conflict)
    assert result.title == "error title"
    assert result.detail == "error detail"
    assert result.code == DBErrorKind.UNIQUE


def test_translate_db_error_returns_internall_for_non_unique(mocker: MockerFixture):
    error = DBError(
        kind=DBErrorKind.OPERATIONAL,
        title="error title",
        detail="error detail",
    )

    result = translate_db_error(error)

    assert isinstance(result, InternalError)
    assert result.title == "error title"
    assert result.detail == "error detail"
    assert result.code == DBErrorKind.OPERATIONAL
