"""Unit tests for the timing and request-logging middleware."""

import logging
import os
import re
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.middleware import (
    RequestLoggingMiddleware,
    TimingMiddleware,
    _sanitize_headers,
)
from app.core.config import get_settings

RESPONSE_TIME_PATTERN = re.compile(r"^\d+\.\d{2}ms$")

MIDDLEWARE_LOGGER = "app.api.middleware"

_ENV_KEYS = (
    "MIDDLEWARE__ENABLE_REQUEST_LOGGING",
    "MIDDLEWARE__SLOW_REQUEST_THRESHOLD",
)


class _RecordCollector(logging.Handler):
    """Collect log records straight off a logger.

    The application's logging config sets ``propagate = False``, so records
    never reach the root handler that ``caplog`` installs. Attaching here keeps
    these tests independent of whether that config has been applied.
    """

    def __init__(self) -> None:
        """Initialise with an empty record buffer."""
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Buffer *record* instead of writing it anywhere.

        Args:
            record: The log record to retain.
        """
        self.records.append(record)

    def messages(self) -> list[str]:
        """Return the formatted message of every captured record."""
        return [record.getMessage() for record in self.records]


@pytest.fixture
def middleware_logs() -> Generator[_RecordCollector, None, None]:
    """Capture records emitted by the middleware logger."""
    logger = logging.getLogger(MIDDLEWARE_LOGGER)
    collector = _RecordCollector()
    original_level = logger.level
    logger.addHandler(collector)
    logger.setLevel(logging.DEBUG)
    try:
        yield collector
    finally:
        logger.removeHandler(collector)
        logger.setLevel(original_level)


@pytest.fixture
def reset_settings() -> Generator[None, None, None]:
    """Clear the settings cache around tests that mutate middleware env vars."""
    get_settings.cache_clear()
    originals = {key: os.environ.get(key) for key in _ENV_KEYS}
    yield
    for key, value in originals.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


def _build_client(*, with_logging: bool = False) -> TestClient:
    """Build a minimal app wrapped with the middleware under test."""
    app = FastAPI()
    app.add_middleware(TimingMiddleware)
    if with_logging:
        app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("kaboom")

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
def test_timing_middleware_adds_response_time_header(reset_settings: None) -> None:
    """Every HTTP response carries a well-formed X-Response-Time header."""
    response = _build_client().get("/ping")

    assert response.status_code == 200
    assert RESPONSE_TIME_PATTERN.match(response.headers["x-response-time"])


@pytest.mark.unit
def test_timing_middleware_sets_header_once(reset_settings: None) -> None:
    """The header appears exactly once on the response."""
    response = _build_client().get("/ping")

    assert len(response.headers.get_list("x-response-time")) == 1


@pytest.mark.unit
def test_slow_request_logs_warning(
    reset_settings: None, middleware_logs: _RecordCollector
) -> None:
    """A request over the threshold produces a warning naming the route."""
    os.environ["MIDDLEWARE__SLOW_REQUEST_THRESHOLD"] = "0.000001"
    get_settings.cache_clear()

    _build_client().get("/ping")

    assert any(
        "Slow request" in message and "/ping" in message
        for message in middleware_logs.messages()
    )


@pytest.mark.unit
def test_fast_request_logs_no_warning(
    reset_settings: None, middleware_logs: _RecordCollector
) -> None:
    """A request under the threshold stays silent."""
    os.environ["MIDDLEWARE__SLOW_REQUEST_THRESHOLD"] = "30"
    get_settings.cache_clear()

    _build_client().get("/ping")

    assert [m for m in middleware_logs.messages() if "Slow request" in m] == []


@pytest.mark.unit
def test_request_logging_disabled_by_default(
    reset_settings: None, middleware_logs: _RecordCollector
) -> None:
    """Request logging stays off unless explicitly enabled."""
    os.environ.pop("MIDDLEWARE__ENABLE_REQUEST_LOGGING", None)
    get_settings.cache_clear()

    response = _build_client(with_logging=True).get("/ping")

    assert response.status_code == 200
    assert [m for m in middleware_logs.messages() if "Request started" in m] == []


@pytest.mark.unit
def test_request_logging_logs_start_and_completion(
    reset_settings: None, middleware_logs: _RecordCollector
) -> None:
    """When enabled, both a start and a completion record are emitted."""
    os.environ["MIDDLEWARE__ENABLE_REQUEST_LOGGING"] = "true"
    get_settings.cache_clear()

    response = _build_client(with_logging=True).get("/ping")

    assert response.status_code == 200
    messages = middleware_logs.messages()
    assert any("Request started: GET /ping" in message for message in messages)
    assert any(
        "Request completed: GET /ping (status: 200)" in message for message in messages
    )


@pytest.mark.unit
def test_request_logging_redacts_sensitive_headers(
    reset_settings: None, middleware_logs: _RecordCollector
) -> None:
    """An Authorization header never reaches the log record."""
    os.environ["MIDDLEWARE__ENABLE_REQUEST_LOGGING"] = "true"
    get_settings.cache_clear()

    _build_client(with_logging=True).get(
        "/ping", headers={"Authorization": "Bearer super-secret"}
    )

    started = [
        record
        for record in middleware_logs.records
        if "Request started" in record.getMessage()
    ]
    assert started, "expected a request-started record"

    headers = started[0].headers  # type: ignore[attr-defined]
    assert headers["authorization"] == "***REDACTED***"
    assert "super-secret" not in str(headers)


@pytest.mark.unit
def test_request_logging_logs_and_reraises_failures(
    reset_settings: None, middleware_logs: _RecordCollector
) -> None:
    """A handler exception is logged and propagated, not swallowed."""
    os.environ["MIDDLEWARE__ENABLE_REQUEST_LOGGING"] = "true"
    get_settings.cache_clear()

    response = _build_client(with_logging=True).get("/boom")

    assert response.status_code == 500
    assert any(
        "Request failed: GET /boom" in message for message in middleware_logs.messages()
    )


@pytest.mark.unit
def test_sanitize_headers_redacts_only_listed_names() -> None:
    """Sanitisation is case-insensitive and leaves other headers intact."""
    result = _sanitize_headers(
        [(b"Authorization", b"Bearer x"), (b"Accept", b"application/json")],
        {"authorization"},
    )

    assert result == {
        "authorization": "***REDACTED***",
        "accept": "application/json",
    }
