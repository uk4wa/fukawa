import enum
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import (
    DBAPIError,
    DisconnectionError,
    IntegrityError,
    InterfaceError,
    InvalidatePoolError,
    OperationalError,
    SQLAlchemyError,
    TimeoutError,
)

from pet.app.errors import (
    VALIDATION_ERROR_TITLE,
    AppError,
    AppErrorCode,
    Conflict,
    InternalError,
    ServiceUnavailable,
    UnprocessableEntity,
)


class PersistenceErrorKind(enum.StrEnum):
    UNIQUE = "unique_violation"
    FK = "fk_violation"
    NOT_NULL = "not_null_violation"
    CHECK = "check_violation"
    OPERATIONAL = "operational"
    UNKNOWN = "unknown"
    OTHER_INTEGRITY = "other_integrity"
    TRANSIENT = "transient"


@dataclass(slots=True)
class PersistenceError(Exception):
    kind: PersistenceErrorKind
    title: str = "Database error"
    status_code: int = 503
    sqlstate: str | None = None
    constraint_name: str | None = None
    table_name: str | None = None
    column_name: str | None = None
    retryable: bool = False
    cause: Exception | None = None
    detail: str | None = None


def get_orig(err: Exception) -> object | None:
    return getattr(err, "orig", None)


def _pg_error_candidates(err: Exception) -> tuple[object, ...]:
    orig = get_orig(err)
    orig_cause = getattr(orig, "__cause__", None)
    orig_context = getattr(orig, "__context__", None)

    return tuple(
        candidate
        for candidate in (
            orig,
            getattr(orig, "diag", None),
            orig_cause,
            getattr(orig_cause, "diag", None),
            orig_context,
            getattr(orig_context, "diag", None),
        )
        if candidate is not None
    )


def _read_pg_str_attr(err: Exception, attr_name: str) -> str | None:
    for candidate in _pg_error_candidates(err):
        value = getattr(candidate, attr_name, None)
        if isinstance(value, str):
            return value

    return None


def pg_sqlstate_from_integrity(err: Exception) -> str | None:
    orig = get_orig(err)

    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def pg_sqlstate_from_dbapi(err: Exception) -> str | None:
    orig = get_orig(err)

    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def pg_constraint_name_from_integrity(err: Exception) -> str | None:
    return _read_pg_str_attr(err, "constraint_name")


def pg_table_name_from_integrity(err: Exception) -> str | None:
    return _read_pg_str_attr(err, "table_name")


def pg_column_name_from_integrity(err: Exception) -> str | None:
    return _read_pg_str_attr(err, "column_name")


type DBDriverError = SQLAlchemyError | OSError


def determine_exc(e: DBDriverError) -> PersistenceError:

    if isinstance(e, IntegrityError):
        kind_map: dict[str, PersistenceErrorKind] = {
            "23505": PersistenceErrorKind.UNIQUE,
            "23503": PersistenceErrorKind.FK,
            "23502": PersistenceErrorKind.NOT_NULL,
            "23514": PersistenceErrorKind.CHECK,
        }

        sqlstate = pg_sqlstate_from_integrity(e)
        constraint_name = pg_constraint_name_from_integrity(e)
        table_name = pg_table_name_from_integrity(e)
        column_name = pg_column_name_from_integrity(e)

        if sqlstate is None:
            kind = PersistenceErrorKind.UNKNOWN
        else:
            kind = kind_map.get(sqlstate, PersistenceErrorKind.UNKNOWN)

        return PersistenceError(
            kind=kind,
            title="db_integrity",
            sqlstate=sqlstate,
            constraint_name=constraint_name,
            table_name=table_name,
            column_name=column_name,
            retryable=False,
            cause=e,
        )

    if isinstance(e, OperationalError):
        return PersistenceError(
            kind=PersistenceErrorKind.OPERATIONAL,
            title="db_unavailable",
            sqlstate=pg_sqlstate_from_dbapi(e),
            retryable=True,
            cause=e,
        )

    if isinstance(e, (InterfaceError, TimeoutError, DisconnectionError, InvalidatePoolError)):
        return PersistenceError(
            kind=PersistenceErrorKind.TRANSIENT,
            title="db_transient",
            sqlstate=pg_sqlstate_from_dbapi(e),
            retryable=True,
            cause=e,
        )

    if isinstance(e, DBAPIError) and e.connection_invalidated:
        return PersistenceError(
            kind=PersistenceErrorKind.TRANSIENT,
            title="db_connection_invalidated",
            sqlstate=pg_sqlstate_from_dbapi(e),
            retryable=True,
            cause=e,
        )

    if isinstance(e, OSError):
        return PersistenceError(
            kind=PersistenceErrorKind.OPERATIONAL,
            title="db_unavailable",
            retryable=True,
            cause=e,
        )

    return PersistenceError(
        kind=PersistenceErrorKind.UNKNOWN,
        title="db_error",
        retryable=False,
        cause=e,
    )


def translate_db_error(error: PersistenceError) -> AppError:
    extra: dict[str, Any] = {
        "retryable": error.retryable,
        "cause": error.cause,
        "constraint_name": error.constraint_name,
        "table_name": error.table_name,
        "column_name": error.column_name,
    }

    match error.kind:
        case PersistenceErrorKind.UNIQUE:
            if error.constraint_name == "uq_organizations_name_canonical":
                return Conflict(
                    title="Conflict",
                    code=AppErrorCode.ORGANIZATION_NAME_TAKEN,
                    detail="Organization name is already taken",
                    extra=extra,
                )
            return Conflict(
                title="Conflict",
                code=AppErrorCode.CONFLICT,
                detail="Resource already exists",
                extra=extra,
            )
        case PersistenceErrorKind.CHECK:
            return UnprocessableEntity(
                title=VALIDATION_ERROR_TITLE,
                code=AppErrorCode.VALIDATION,
                detail="Stored value violates validation rules",
                extra=extra,
            )
        case PersistenceErrorKind.NOT_NULL:
            field_name = error.column_name or "field"
            return UnprocessableEntity(
                title=VALIDATION_ERROR_TITLE,
                code=AppErrorCode.VALIDATION,
                detail=f'Field "{field_name}" cannot be null',
                extra=extra,
            )
        case PersistenceErrorKind.OPERATIONAL | PersistenceErrorKind.TRANSIENT:
            return ServiceUnavailable(
                title="Service Unavailable",
                code=AppErrorCode.SERVICE_UNAVAILABLE,
                detail="Temporary service outage",
                extra={
                    **extra,
                    "sqlstate": error.sqlstate,
                },
            )
        case _:
            return InternalError(
                title="Internal Server Error",
                code=AppErrorCode.INTERNAL_ERROR,
                detail="Unexpected error",
                extra={
                    **extra,
                    "sqlstate": error.sqlstate,
                },
            )


class UoWNotInitializedError(RuntimeError):
    def __init__(self, field: str) -> None:
        super().__init__(f"UnitOfWork is not started: '{field}' is not initialized")
        self.field = field
