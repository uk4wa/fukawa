from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from pet.api.exceptions_handler import register_exception_handlers
from pet.api.http_logging import register_http_logging
from pet.domain.exc import AppError


def test_handled_error_response_includes_request_id(mocker: MockerFixture) -> None:
    app = FastAPI()
    http_logger = Mock()
    errors_logger = Mock()

    mocker.patch("pet.api.http_logging.logger", http_logger)
    mocker.patch("pet.api.exceptions_handler.logger", errors_logger)

    register_http_logging(app)
    register_exception_handlers(app)

    @app.get("/handled")
    async def handled() -> None:  # type: ignore
        raise AppError(title="bad request", code="bad_request", detail="oops")

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/handled")

    assert response.status_code == 400
    assert response.headers["x-request-id"]
    assert response.json()["request_id"] == response.headers["x-request-id"]
    http_logger.warning.assert_called_once()
    errors_logger.exception.assert_not_called()


def test_unhandled_error_response_includes_request_id_without_duplicate_http_error_log(
    mocker: MockerFixture,
) -> None:
    app = FastAPI()
    http_logger = Mock()
    errors_logger = Mock()

    mocker.patch("pet.api.http_logging.logger", http_logger)
    mocker.patch("pet.api.exceptions_handler.logger", errors_logger)

    register_http_logging(app)
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:  # type: ignore
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.headers["x-request-id"]
    assert response.json()["request_id"] == response.headers["x-request-id"]
    http_logger.exception.assert_not_called()
    errors_logger.exception.assert_called_once()
