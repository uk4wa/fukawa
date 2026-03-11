import pytest
from pytest_mock import MockerFixture

from pet.domain.exc import DBError, DBErrorKind
from sqlalchemy.exc import IntegrityError, OperationalError
from pet.infra.sqla.db.exc import pg_sqlstate_from_integrity, determine_exc

# determine_exc tests


@pytest.mark.parametrize(
    ("sqlstate", "expected_kind"),
    [
        ("23505", DBErrorKind.UNIQUE),
        ("23503", DBErrorKind.FK),
        ("23502", DBErrorKind.NOT_NULL),
        ("23514", DBErrorKind.CHECK),
        (None, DBErrorKind.UNKNOWN),
    ],
)
def test_determine_exc_integrity_ok(
    mocker: MockerFixture,
    sqlstate: str | None,
    expected_kind: DBErrorKind,
):
    err = IntegrityError(
        statement="statement", params={"name": "acme"}, orig=Exception()
    )

    pg_sqlstate_mock = mocker.patch(
        "pet.infra.sqla.db.exc.pg_sqlstate_from_integrity",
        return_value=sqlstate,
    )

    result = determine_exc(err)

    assert isinstance(result, DBError)
    assert result.kind == expected_kind
    pg_sqlstate_mock.assert_called_once_with(err)


def test_determine_exc_operational_ok(mocker: MockerFixture):
    err = OperationalError(
        statement="statement", params={"name": "acme"}, orig=Exception()
    )

    result = determine_exc(err)

    assert isinstance(result, DBError)
    assert result.kind == DBErrorKind.OPERATIONAL


def test_determine_exc_unknown_ok(mocker: MockerFixture):
    err = Exception()

    result = determine_exc(err)  # type: ignore

    assert isinstance(result, DBError)
    assert result.kind == DBErrorKind.UNKNOWN


# pg_sqlstate_from_integrity tests


def test_pg_sqlstate_from_integrity_success_with_sqlstate(mocker: MockerFixture):
    exc = mocker.Mock()
    exc.orig = mocker.Mock()
    exc.orig.sqlstate = "51322"

    result = pg_sqlstate_from_integrity(err=exc)

    assert result == "51322"


def test_pg_sqlstate_from_integrity_failed_with_sqlstate(mocker: MockerFixture):
    exc = mocker.Mock()
    exc.orig = mocker.Mock()
    exc.orig.sqlstate = "51322"

    result = pg_sqlstate_from_integrity(err=exc)

    assert not result == "51321"
