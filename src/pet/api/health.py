import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from pet.infra.sqla.db.exc import DB_OPERATION_ERRORS

health = APIRouter()


class HealthStatus(BaseModel):
    status: str


@health.get("/healthz", response_model=HealthStatus, include_in_schema=False)
async def healthz() -> HealthStatus:
    return HealthStatus(status="ok")


DB_NOT_READY_DETAIL = "Service is not ready"


@health.get("/readyz", response_model=HealthStatus, include_in_schema=False)
async def readyz(request: Request) -> HealthStatus:
    try:
        async with request.app.state.engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
    except DB_OPERATION_ERRORS as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=DB_NOT_READY_DETAIL,
        ) from e

    return HealthStatus(status="ok")
