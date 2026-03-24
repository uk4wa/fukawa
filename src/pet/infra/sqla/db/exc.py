from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from pet.domain.exc import DBError, DBErrorKind


def get_orig(err: Exception):
    return getattr(err, "orig", None)


def pg_sqlstate_from_integrity(err: Exception) -> str | None:
    orig = get_orig(err)

    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def pg_constraint_name_from_integrity(err: Exception) -> str | None:
    orig = get_orig(err)
    orig_cause = getattr(orig, "__cause__", None)
    orig_context = getattr(orig, "__context__", None)

    return (
        getattr(orig, "constraint_name", None)
        or getattr(getattr(orig, "diag", None), "constraint_name", None)
        or getattr(orig_cause, "constraint_name", None)
        or getattr(getattr(orig_cause, "diag", None), "constraint_name", None)
        or getattr(orig_context, "constraint_name", None)
        or getattr(getattr(orig_context, "diag", None), "constraint_name", None)
    )


def determine_exc(e: SQLAlchemyError) -> DBError:

    if isinstance(e, IntegrityError):
        kind_map: dict[str, DBErrorKind] = {
            "23505": DBErrorKind.UNIQUE,
            "23503": DBErrorKind.FK,
            "23502": DBErrorKind.NOT_NULL,
            "23514": DBErrorKind.CHECK,
        }

        sqlstate = pg_sqlstate_from_integrity(e)
        constraint_name = pg_constraint_name_from_integrity(e)

        if sqlstate is None:
            kind = DBErrorKind.UNKNOWN
        else:
            kind = kind_map.get(sqlstate, DBErrorKind.UNKNOWN)

        return DBError(
            kind=kind,
            title="db_integrity",
            sqlstate=sqlstate,
            constraint_name=constraint_name,
            retryable=False,
            cause=e,
        )

    if isinstance(e, OperationalError):
        return DBError(
            kind=DBErrorKind.OPERATIONAL,
            title="db_unavailable",
            retryable=True,
            cause=e,
        )

    return DBError(
        kind=DBErrorKind.UNKNOWN,
        title="db_error",
        retryable=False,
        cause=e,
    )


class UoWNotInitializedError(RuntimeError):
    def __init__(self, field: str):
        super().__init__(f"UnitOfWork is not started: '{field}' is not initialized")
        self.field = field
