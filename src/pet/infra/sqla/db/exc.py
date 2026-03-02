from pet.domain.exc import DBError, DBErrorKind
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError


def pg_sqlstate_from_integrity(err: Exception) -> str | None:
    orig = getattr(err, "orig", None)

    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def determine_exc(e: SQLAlchemyError) -> DBError:

    if isinstance(e, IntegrityError):

        kind_map: dict[str, DBErrorKind] = {
            "23505": DBErrorKind.UNIQUE,
            "23503": DBErrorKind.FK,
            "23502": DBErrorKind.NOT_NULL,
            "23514": DBErrorKind.CHECK,
        }

        sqlstate = pg_sqlstate_from_integrity(e)

        if sqlstate is None:
            kind = DBErrorKind.UNKNOWN
        else:
            kind = kind_map.get(sqlstate, DBErrorKind.UNKNOWN)

        return DBError(
            kind=kind,
            title="db_integrity",
            sqlstate=sqlstate,
            retryable=False,
            cause=e,
        )

    if isinstance(e, OperationalError):
        return DBError(
            kind=DBErrorKind.OPERATIONAL,
            title="db_unvailable",
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
