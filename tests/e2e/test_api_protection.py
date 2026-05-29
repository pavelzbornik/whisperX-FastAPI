"""End-to-end tests for API-wide protection (issue #533).

Covers upload-size cap (413), per-caller rate limiting (429), route-level
concurrency caps (503), and bearer-token auth (401) on one synchronous endpoint
(``/v1/audio/transcriptions``) and one asynchronous endpoint
(``/service/transcribe``), plus the no-op-by-default behavior.

All features read settings per request, so each test toggles the relevant
``*`` environment variables, clears the cached settings/gates, and resets the
rate limiter — no app rebuild required.
"""

from collections.abc import Generator
from typing import Any

import pytest
from pytest import MonkeyPatch
from dependency_injector import providers
from fastapi.testclient import TestClient
from unittest.mock import patch

import app.main as main_module
from app.api.dependencies import get_task_repository
from app.core.concurrency import (
    get_async_concurrency_gate,
    get_sync_concurrency_gate,
)
from app.core.config import get_settings
from app.core.rate_limit import reset_rate_limiter
from app.domain.entities.task import Task as DomainTask
from tests.mocks import MockAlignmentService, MockTranscriptionService

SYNC_ENDPOINT = "/v1/audio/transcriptions"
ASYNC_ENDPOINT = "/service/transcribe"
AUDIO_BYTES = b"dummy-audio-bytes"


class _FakeTaskRepository:
    """In-memory task repository so protection tests never touch the database."""

    def __init__(self) -> None:
        self.added: list[DomainTask] = []
        self.updates: list[tuple[str, dict[str, Any]]] = []

    async def add(self, task: DomainTask) -> str:
        self.added.append(task)
        return task.uuid

    async def update(self, identifier: str, update_data: dict[str, Any]) -> None:
        self.updates.append((identifier, update_data))

    async def get_by_id(self, identifier: str) -> DomainTask | None:
        return None

    async def get_all(self) -> list[DomainTask]:
        return list(self.added)

    async def delete(self, identifier: str) -> bool:
        return True


def _reset_runtime_caches() -> None:
    """Reset cached settings, concurrency gates, and rate-limit storage."""
    get_settings.cache_clear()
    get_sync_concurrency_gate.cache_clear()
    get_async_concurrency_gate.cache_clear()
    reset_rate_limiter()


@pytest.fixture
def protected_client(monkeypatch: MonkeyPatch) -> Generator[TestClient, None, None]:
    """A TestClient with mocked ML services and DB-free, audio-free success paths."""
    container = main_module.container
    container.transcription_service.override(
        providers.Object(MockTranscriptionService())
    )
    container.alignment_service.override(providers.Object(MockAlignmentService()))

    fake_repo = _FakeTaskRepository()
    main_module.app.dependency_overrides[get_task_repository] = lambda: fake_repo

    # Make audio decoding and background processing no-ops so the success path is
    # fast and deterministic without ffmpeg or the database.
    for module in ("app.api.openai_compat_api", "app.api.audio_services_api"):
        monkeypatch.setattr(f"{module}.process_audio_file", lambda *_a, **_k: "AUDIO")
        monkeypatch.setattr(f"{module}.get_audio_duration", lambda *_a, **_k: 1.0)
    monkeypatch.setattr(
        "app.api.audio_services_api.process_transcribe", lambda *_a, **_k: None
    )

    _reset_runtime_caches()

    with (
        patch("app.main.save_openapi_json"),
        patch("app.main.generate_db_schema"),
        TestClient(main_module.app, follow_redirects=False) as client,
    ):
        yield client

    main_module.app.dependency_overrides.pop(get_task_repository, None)
    container.transcription_service.reset_override()
    container.alignment_service.reset_override()
    _reset_runtime_caches()


def _post(
    client: TestClient, endpoint: str, headers: dict[str, str] | None = None
) -> Any:
    """Post a small valid multipart transcription request to ``endpoint``."""
    files: list[tuple[str, Any]] = [("file", ("audio.mp3", AUDIO_BYTES, "audio/mpeg"))]
    if endpoint == SYNC_ENDPOINT:
        files.append(("model", (None, "whisper-1")))
    return client.post(endpoint, files=files, headers=headers)


@pytest.mark.e2e
@pytest.mark.parametrize("endpoint", [SYNC_ENDPOINT, ASYNC_ENDPOINT])
def test_no_protection_by_default(protected_client: TestClient, endpoint: str) -> None:
    """With all features off (defaults), requests succeed unprotected."""
    response = _post(protected_client, endpoint)
    assert response.status_code == 200


# --- Upload size cap (413) ---------------------------------------------------


@pytest.mark.e2e
@pytest.mark.parametrize("endpoint", [SYNC_ENDPOINT, ASYNC_ENDPOINT])
def test_oversize_upload_rejected(
    protected_client: TestClient, monkeypatch: MonkeyPatch, endpoint: str
) -> None:
    """A body exceeding MAX_UPLOAD_SIZE_MB is rejected with 413."""
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
    get_settings.cache_clear()

    response = protected_client.post(endpoint, content=b"x" * (2 * 1024 * 1024))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


# --- Rate limiting (429) -----------------------------------------------------


@pytest.mark.e2e
@pytest.mark.parametrize("endpoint", [SYNC_ENDPOINT, ASYNC_ENDPOINT])
def test_rate_limit_trips_after_budget(
    protected_client: TestClient, monkeypatch: MonkeyPatch, endpoint: str
) -> None:
    """Exceeding the per-minute/burst budget returns 429 with Retry-After."""
    monkeypatch.setenv("RATE_LIMIT__ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT__REQUESTS_PER_MINUTE", "1")
    monkeypatch.setenv("RATE_LIMIT__BURST", "1")
    _reset_runtime_caches()

    first = _post(protected_client, endpoint)
    assert first.status_code == 200

    second = _post(protected_client, endpoint)
    assert second.status_code == 429
    assert "Retry-After" in second.headers
    assert second.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


# --- Route concurrency cap (503) ---------------------------------------------


@pytest.mark.e2e
@pytest.mark.parametrize(
    ("endpoint", "gate_getter"),
    [
        (SYNC_ENDPOINT, get_sync_concurrency_gate),
        (ASYNC_ENDPOINT, get_async_concurrency_gate),
    ],
)
def test_concurrency_cap_trips_when_full(
    protected_client: TestClient,
    monkeypatch: MonkeyPatch,
    endpoint: str,
    gate_getter: Any,
) -> None:
    """When the path's concurrency budget is exhausted, requests get 503."""
    monkeypatch.setenv("MAX_QUEUED_GPU_REQUESTS", "2")
    monkeypatch.setenv("SYNC_GPU_QUOTA_FRACTION", "0.5")
    _reset_runtime_caches()

    gate = gate_getter()  # capacity 1 for each path
    assert gate.acquire() is True  # occupy the only slot
    try:
        response = _post(protected_client, endpoint)
    finally:
        gate.release()

    assert response.status_code == 503
    assert "Retry-After" in response.headers
    assert response.json()["error"]["code"] == "SERVICE_OVERLOADED"


# --- Bearer-token auth (401) -------------------------------------------------


@pytest.mark.e2e
@pytest.mark.parametrize("endpoint", [SYNC_ENDPOINT, ASYNC_ENDPOINT])
def test_auth_required_when_enabled(
    protected_client: TestClient, monkeypatch: MonkeyPatch, endpoint: str
) -> None:
    """With auth enabled, a missing token is rejected and a valid token passes."""
    monkeypatch.setenv("AUTH__ENABLED", "true")
    monkeypatch.setenv("AUTH__BEARER_TOKEN", "s3cret")
    get_settings.cache_clear()

    missing = _post(protected_client, endpoint)
    assert missing.status_code == 401
    assert missing.headers["WWW-Authenticate"] == "Bearer"
    assert missing.json()["error"]["code"] == "AUTHENTICATION_FAILED"

    authorized = _post(
        protected_client, endpoint, headers={"Authorization": "Bearer s3cret"}
    )
    assert authorized.status_code == 200
