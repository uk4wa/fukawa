import logging

from pet.config.logging import _UvicornAccessHealthcheckFilter


def _make_access_record(msg: str, args: tuple[object, ...]) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )


def test_uvicorn_access_filter_skips_readyz_path() -> None:
    record = _make_access_record(
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:42124", "GET", "/readyz", "1.1", 200),
    )

    assert not _UvicornAccessHealthcheckFilter().filter(record)


def test_uvicorn_access_filter_keeps_non_healthcheck_path() -> None:
    record = _make_access_record(
        '%s - "%s %s HTTP/%s" %d',
        ("172.18.0.1:44056", "GET", "/docs", "1.1", 200),
    )

    assert _UvicornAccessHealthcheckFilter().filter(record)


def test_uvicorn_access_filter_skips_healthcheck_path_from_rendered_message() -> None:
    record = _make_access_record(
        '127.0.0.1:42124 - "GET /readyz?probe=1 HTTP/1.1" 200',
        (),
    )

    assert not _UvicornAccessHealthcheckFilter().filter(record)
