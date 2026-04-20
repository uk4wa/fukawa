import pytest
from fastapi import FastAPI, Response
from httpx import ASGITransport, AsyncClient

from pet.api.middleware.http_logging import register_http_logging


@pytest.mark.asyncio
async def test_http_logging_skips_healthcheck_paths(mocker) -> None:
    app = FastAPI()
    register_http_logging(app)

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        return {"status": "ok"}

    info_mock = mocker.patch("pet.api.middleware.http_logging.logger.info")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    info_mock.assert_not_called()


@pytest.mark.asyncio
async def test_http_logging_logs_successful_requests(mocker) -> None:
    app = FastAPI()
    register_http_logging(app)

    @app.post("/orgs/")
    async def create_org() -> Response:
        return Response(status_code=201)

    info_mock = mocker.patch("pet.api.middleware.http_logging.logger.info")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/orgs/")

    assert response.status_code == 201
    info_mock.assert_called_once()
    assert info_mock.call_args.args == ("http_request_finished",)
    assert info_mock.call_args.kwargs["status_code"] == 201
    assert isinstance(info_mock.call_args.kwargs["duration_ms"], float)


@pytest.mark.asyncio
async def test_http_logging_logs_4xx_as_warning(mocker) -> None:
    app = FastAPI()
    register_http_logging(app)

    @app.post("/orgs/")
    async def create_org() -> Response:
        return Response(status_code=409)

    warning_mock = mocker.patch("pet.api.middleware.http_logging.logger.warning")
    info_mock = mocker.patch("pet.api.middleware.http_logging.logger.info")
    error_mock = mocker.patch("pet.api.middleware.http_logging.logger.error")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/orgs/")

    assert response.status_code == 409
    warning_mock.assert_called_once()
    info_mock.assert_not_called()
    error_mock.assert_not_called()
