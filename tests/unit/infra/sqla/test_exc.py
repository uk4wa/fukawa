import pytest
from pytest_mock import MockerFixture
from sqlalchemy.exc import (
    DBAPIError,
    DisconnectionError,
    IntegrityError,
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
    TimeoutError,
)

from pet.app.errors import (
    AppError,
    Conflict,
    InternalError,
    ServiceUnavailable,
    UnprocessableEntity,
)
from pet.infra.sqla.db.exc import (
    PersistenceError,
    PersistenceErrorKind,
    determine_exc,
    pg_column_name_from_integrity,
    pg_constraint_name_from_integrity,
    pg_sqlstate_from_integrity,
    pg_table_name_from_integrity,
    translate_db_error,
)


@pytest.mark.parametrize(
    ("sqlstate", "expected_kind"),
    [
        ("23505", PersistenceErrorKind.UNIQUE),
        ("23503", PersistenceErrorKind.FK),
        ("23502", PersistenceErrorKind.NOT_NULL),
        ("23514", PersistenceErrorKind.CHECK),
        ("99999", PersistenceErrorKind.UNKNOWN),
        (None, PersistenceErrorKind.UNKNOWN),
    ],
)
def test_determine_exc_maps_integrity_sqlstate(
    mocker: MockerFixture,
    sqlstate: str | None,
    expected_kind: PersistenceErrorKind,
):
    error = IntegrityError(
        statement="statement",
        params={"name": "acme"},
        orig=Exception(),
    )

    pg_sqlstate_mock = mocker.patch(
        "pet.infra.sqla.db.exc.pg_sqlstate_from_integrity",
        return_value=sqlstate,
    )

    result = determine_exc(error)

    assert result.kind == expected_kind
    assert result.title == "db_integrity"
    assert not result.retryable
    assert result.sqlstate == sqlstate
    assert result.constraint_name is None
    assert result.table_name is None
    assert result.column_name is None
    assert result.cause is error

    pg_sqlstate_mock.assert_called_once_with(error)


def test_determine_exc_maps_operational_error(mocker: MockerFixture):
    error = OperationalError(statement="statement", params={"name": "acme"}, orig=Exception())

    result = determine_exc(error)

    assert result.kind == PersistenceErrorKind.OPERATIONAL
    assert result.title == "db_unavailable"
    assert result.retryable
    assert result.sqlstate is None
    assert result.cause is error


@pytest.mark.parametrize(
    ("error", "expected_title"),
    [
        (InterfaceError(statement="statement", params={"name": "acme"}, orig=Exception()), "db_transient"),
        (TimeoutError("pool timeout"), "db_transient"),
        (DisconnectionError(), "db_transient"),
    ],
)
def test_determine_exc_maps_transient_sqla_errors(
    error: SQLAlchemyError,
    expected_title: str,
) -> None:
    result = determine_exc(error)

    assert result.kind == PersistenceErrorKind.TRANSIENT
    assert result.title == expected_title
    assert result.retryable is True
    assert result.cause is error


def test_determine_exc_maps_connection_invalidated_dbapi_error() -> None:
    error = DBAPIError(
        statement="statement",
        params={"name": "acme"},
        orig=Exception(),
        connection_invalidated=True,
    )

    result = determine_exc(error)

    assert result.kind == PersistenceErrorKind.TRANSIENT
    assert result.title == "db_connection_invalidated"
    assert result.retryable is True
    assert result.cause is error


def test_determine_exc_maps_unknown_sqla_error(mocker: MockerFixture):
    error = SQLAlchemyError("unknown")

    result = determine_exc(error)

    assert isinstance(result, PersistenceError)
    assert result.kind == PersistenceErrorKind.UNKNOWN
    assert result.title == "db_error"
    assert result.retryable is False
    assert result.cause is error


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


def test_pg_constraint_name_from_integrity_reads_constraint_name(mocker: MockerFixture) -> None:
    error = mocker.Mock()
    error.orig = mocker.Mock(constraint_name="uq_organizations_name_canonical")

    result = pg_constraint_name_from_integrity(error)

    assert result == "uq_organizations_name_canonical"


def test_pg_table_name_from_integrity_reads_table_name_from_diag(mocker: MockerFixture) -> None:
    error = mocker.Mock()
    error.orig = mocker.Mock(diag=mocker.Mock(table_name="organizations"))

    result = pg_table_name_from_integrity(error)

    assert result == "organizations"


def test_pg_column_name_from_integrity_reads_column_name(mocker: MockerFixture) -> None:
    error = mocker.Mock()
    error.orig = mocker.Mock(column_name="name")

    result = pg_column_name_from_integrity(error)

    assert result == "name"


def test_determine_exc_extracts_table_and_column_for_not_null(mocker: MockerFixture) -> None:
    error = IntegrityError(
        statement="statement",
        params={"name": None},
        orig=mocker.Mock(
            sqlstate="23502",
            constraint_name=None,
            table_name="organizations",
            column_name="name",
        ),
    )

    result = determine_exc(error)

    assert result.kind == PersistenceErrorKind.NOT_NULL
    assert result.sqlstate == "23502"
    assert result.constraint_name is None
    assert result.table_name == "organizations"
    assert result.column_name == "name"


def test_translate_db_error_returns_conflict_for_unique(mocker: MockerFixture):
    error = PersistenceError(
        kind=PersistenceErrorKind.UNIQUE,
        title="error title",
        detail="error detail",
        constraint_name="uq_organizations_name_canonical",
    )

    result = translate_db_error(error)

    assert isinstance(result, Conflict)
    assert result.title == "Conflict"
    assert result.detail == "Organization name is already taken"
    assert result.code == "organization_name_taken"


def test_translate_db_error_returns_internall_for_non_unique(mocker: MockerFixture):
    error = PersistenceError(
        kind=PersistenceErrorKind.OPERATIONAL,
        title="error title",
        detail="error detail",
    )

    result = translate_db_error(error)

    assert isinstance(result, ServiceUnavailable)
    assert result.title == "Service Unavailable"
    assert result.detail == "Temporary service outage"
    assert result.code == "service_unavailable"


def test_translate_db_error_returns_generic_conflict_for_unknown_unique_constraint() -> None:
    error = PersistenceError(
        kind=PersistenceErrorKind.UNIQUE,
        constraint_name="uq_unknown_unique",
    )

    result = translate_db_error(error)

    assert isinstance(result, Conflict)
    assert result.code == "conflict"


def test_translate_db_error_returns_generic_validation_error_for_check_constraint() -> None:
    error = PersistenceError(
        kind=PersistenceErrorKind.CHECK,
        constraint_name="ck_organizations_name_casefold_max_len",
    )

    result = translate_db_error(error)

    assert isinstance(result, UnprocessableEntity)
    assert result.code == "validation_error"
    assert result.detail == "Stored value violates validation rules"


def test_translate_db_error_returns_validation_error_for_not_null_column() -> None:
    error = PersistenceError(
        kind=PersistenceErrorKind.NOT_NULL,
        table_name="organizations",
        column_name="name",
    )

    result = translate_db_error(error)

    assert isinstance(result, UnprocessableEntity)
    assert result.code == "validation_error"
    assert result.detail == 'Field "name" cannot be null'


def test_translate_db_error_returns_internal_error_for_unknown_db_error() -> None:
    error = PersistenceError(kind=PersistenceErrorKind.UNKNOWN)

    result = translate_db_error(error)

    assert isinstance(result, InternalError)
    assert isinstance(result, AppError)
    assert result.code == "internal_error"
