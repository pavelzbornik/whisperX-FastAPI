"""Unit tests for the upload size cap middleware."""

import os
from collections.abc import Generator

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.middleware import MaxUploadSizeMiddleware
from app.core.config import get_settings


def _build_client() -> TestClient:
    """Build a minimal app wrapped with the upload size middleware."""
    app = FastAPI()
    app.add_middleware(MaxUploadSizeMiddleware)

    @app.post("/echo")
    async def echo(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"received": len(body)}

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


@pytest.fixture
def reset_settings() -> Generator[None, None, None]:
    """Clear the settings cache around each test that mutates env vars."""
    get_settings.cache_clear()
    original = os.environ.get("MAX_UPLOAD_SIZE_MB")
    yield
    if original is None:
        os.environ.pop("MAX_UPLOAD_SIZE_MB", None)
    else:
        os.environ["MAX_UPLOAD_SIZE_MB"] = original
    get_settings.cache_clear()


@pytest.mark.unit
def test_oversize_upload_rejected_with_413(reset_settings: None) -> None:
    """A body larger than the cap is rejected with 413 before reaching the route."""
    os.environ["MAX_UPLOAD_SIZE_MB"] = "1"
    get_settings.cache_clear()
    client = _build_client()

    response = client.post("/echo", content=b"x" * (2 * 1024 * 1024))

    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "REQUEST_TOO_LARGE"
    assert body["error"]["type"] == "invalid_request_error"


@pytest.mark.unit
def test_upload_within_cap_passes(reset_settings: None) -> None:
    """A body within the cap reaches the route handler."""
    os.environ["MAX_UPLOAD_SIZE_MB"] = "1"
    get_settings.cache_clear()
    client = _build_client()

    response = client.post("/echo", content=b"x" * 1024)

    assert response.status_code == 200
    assert response.json()["received"] == 1024


@pytest.mark.unit
def test_zero_cap_is_unlimited(reset_settings: None) -> None:
    """A cap of 0 disables enforcement (default no-op behavior)."""
    os.environ["MAX_UPLOAD_SIZE_MB"] = "0"
    get_settings.cache_clear()
    client = _build_client()

    response = client.post("/echo", content=b"x" * (3 * 1024 * 1024))

    assert response.status_code == 200


@pytest.mark.unit
def test_get_requests_not_checked(reset_settings: None) -> None:
    """GET requests bypass the body-size check."""
    os.environ["MAX_UPLOAD_SIZE_MB"] = "1"
    get_settings.cache_clear()
    client = _build_client()

    response = client.get("/ping")

    assert response.status_code == 200


@pytest.mark.unit
async def test_malformed_content_length_passes_through(reset_settings: None) -> None:
    """A non-numeric Content-Length is treated as unknown and not rejected."""
    os.environ["MAX_UPLOAD_SIZE_MB"] = "1"
    get_settings.cache_clear()

    reached: list[str] = []

    async def inner(scope: dict, receive: object, send: object) -> None:
        reached.append("inner")

    middleware = MaxUploadSizeMiddleware(inner)
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"content-length", b"not-a-number")],
    }

    async def receive() -> dict:
        return {"type": "http.request", "body": b""}

    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    await middleware(scope, receive, send)

    assert reached == ["inner"]
    assert sent == []
