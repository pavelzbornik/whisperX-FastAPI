"""Unit tests for the OpenAI-compatible API endpoints."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from dependency_injector import providers
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as main_module
from app.api.dependencies import get_task_repository
from app.domain.entities.task import Task as DomainTask
from app.schemas import (
    ASROptions,
    ComputeType,
    Device,
    TaskEnum,
    TaskStatus,
    TaskType,
    WhisperModel,
    WhisperModelParams,
)
from tests.mocks import MockAlignmentService, MockTranscriptionService

AUDIO_FILE = "tests/test_files/audio_en.mp3"


class _FakeTaskRepository:
    """In-memory task repository that records add/update calls for assertions."""

    def __init__(self) -> None:
        """Initialize empty call records."""
        self.added: list[DomainTask] = []
        self.updates: list[tuple[str, dict[str, Any]]] = []

    async def add(self, task: DomainTask) -> str:
        """Record the added task and return its identifier."""
        self.added.append(task)
        return task.uuid

    async def update(self, identifier: str, update_data: dict[str, Any]) -> None:
        """Record an update call."""
        self.updates.append((identifier, update_data))

    async def get_by_id(self, identifier: str) -> DomainTask | None:
        """Return None — not used by these tests."""
        return None

    async def get_all(self) -> list[DomainTask]:
        """Return all recorded tasks."""
        return list(self.added)

    async def delete(self, identifier: str) -> bool:
        """No-op delete returning True."""
        return True


@pytest.fixture
def openai_client() -> Generator[
    tuple[TestClient, MockTranscriptionService, MockAlignmentService], None, None
]:
    """Provide a test client with mocked transcription and alignment services."""
    container = main_module.container
    mock_transcription_service = MockTranscriptionService()
    mock_alignment_service = MockAlignmentService()

    container.transcription_service.override(
        providers.Object(mock_transcription_service)
    )
    container.alignment_service.override(providers.Object(mock_alignment_service))

    with (
        patch("app.main.save_openapi_json"),
        patch("app.main.generate_db_schema"),
        TestClient(main_module.app, follow_redirects=False) as client,
    ):
        yield client, mock_transcription_service, mock_alignment_service

    container.transcription_service.reset_override()
    container.alignment_service.reset_override()


@pytest.fixture
def openai_client_with_repo() -> Generator[
    tuple[TestClient, _FakeTaskRepository], None, None
]:
    """Provide a test client with mocked ML services and a fake task repository."""
    container = main_module.container
    container.transcription_service.override(
        providers.Object(MockTranscriptionService())
    )
    container.alignment_service.override(providers.Object(MockAlignmentService()))

    fake_repo = _FakeTaskRepository()
    main_module.app.dependency_overrides[get_task_repository] = lambda: fake_repo

    with (
        patch("app.main.save_openapi_json"),
        patch("app.main.generate_db_schema"),
        TestClient(main_module.app, follow_redirects=False) as client,
    ):
        yield client, fake_repo

    main_module.app.dependency_overrides.pop(get_task_repository, None)
    container.transcription_service.reset_override()
    container.alignment_service.reset_override()


def _post_openai_request(
    client: TestClient,
    *,
    endpoint: str = "/v1/audio/transcriptions",
    headers: dict[str, str] | None = None,
    extra_fields: list[tuple[str, Any]] | None = None,
) -> Any:
    """Post a multipart OpenAI-compatible transcription request."""
    files: list[tuple[str, Any]] = []
    if extra_fields:
        files.extend((name, (None, value)) for name, value in extra_fields)

    with open(AUDIO_FILE, "rb") as audio_file:
        files.append(("file", ("audio_en.mp3", audio_file, "audio/mpeg")))
        files.append(("model", (None, "whisper-1")))
        return client.post(endpoint, files=files, headers=headers)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("response_format", "expected_content_type", "expected_body_fragment"),
    [
        ("json", "application/json", '"text":"This is a test transcription."'),
        ("text", "text/plain", "This is a test transcription."),
        ("srt", "application/x-subrip", "1\n00:00:00,000 --> 00:00:02,000"),
        ("vtt", "text/vtt", "WEBVTT"),
        ("verbose_json", "application/json", '"task":"transcribe"'),
    ],
)
def test_openai_transcription_response_formats(
    openai_client: tuple[TestClient, MockTranscriptionService, MockAlignmentService],
    response_format: str,
    expected_content_type: str,
    expected_body_fragment: str,
) -> None:
    """Each supported response format should return the expected media type."""
    client, _, _ = openai_client

    response = _post_openai_request(
        client,
        extra_fields=[("response_format", response_format)],
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(expected_content_type)
    assert expected_body_fragment in response.text


@pytest.mark.unit
def test_openai_transcription_word_timestamps_trigger_alignment(
    openai_client: tuple[TestClient, MockTranscriptionService, MockAlignmentService],
) -> None:
    """Word timestamps should trigger alignment and include words in verbose JSON."""
    client, _, mock_alignment_service = openai_client

    response = _post_openai_request(
        client,
        extra_fields=[
            ("response_format", "verbose_json"),
            ("timestamp_granularities[]", "word"),
        ],
    )

    assert response.status_code == 200
    data = response.json()
    assert "words" in data
    assert data["words"]
    assert mock_alignment_service.align_called is True


@pytest.mark.unit
def test_openai_transcription_accepts_authorization_header(
    openai_client: tuple[TestClient, MockTranscriptionService, MockAlignmentService],
) -> None:
    """Bearer authorization headers should be accepted and ignored."""
    client, _, _ = openai_client

    response = _post_openai_request(
        client,
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 200
    assert response.json()["text"] == "This is a test transcription."


@pytest.mark.unit
def test_openai_translation_uses_translate_task(
    openai_client: tuple[TestClient, MockTranscriptionService, MockAlignmentService],
) -> None:
    """The translations endpoint should set the Whisper task to translate."""
    client, mock_transcription_service, _ = openai_client

    response = _post_openai_request(
        client,
        endpoint="/v1/audio/translations",
    )

    assert response.status_code == 200
    assert mock_transcription_service.last_transcribe_params["task"] == "translate"


@pytest.mark.unit
def test_openai_timestamp_granularities_require_verbose_json(
    openai_client: tuple[TestClient, MockTranscriptionService, MockAlignmentService],
) -> None:
    """Non-verbose responses should reject timestamp granularities."""
    client, _, _ = openai_client

    response = _post_openai_request(
        client,
        extra_fields=[
            ("timestamp_granularities[]", "word"),
        ],
    )

    assert response.status_code == 422
    assert response.json()["error"]["type"] == "invalid_request_error"


def _post_openai_request_with_filename(
    client: TestClient,
    *,
    filename: str,
    content_type: str = "application/octet-stream",
) -> Any:
    """Post an OpenAI-compatible request using a custom filename."""
    files = [
        ("file", (filename, b"not really audio", content_type)),
        ("model", (None, "whisper-1")),
    ]
    return client.post("/v1/audio/transcriptions", files=files)


@pytest.mark.unit
def test_openai_unsupported_extension_returns_openai_envelope(
    openai_client: tuple[TestClient, MockTranscriptionService, MockAlignmentService],
) -> None:
    """Unsupported file extensions must return the OpenAI-style error envelope."""
    client, _, _ = openai_client

    response = _post_openai_request_with_filename(client, filename="malware.xyz")

    assert response.status_code == 422
    body = response.json()
    assert "error" in body
    assert body["error"]["type"] == "invalid_request_error"
    assert "detail" not in body


def _make_cuda_whisper_params() -> tuple[WhisperModelParams, ASROptions]:
    """Build cuda-targeted Whisper params for forcing the GPU-semaphore branch."""
    model_params = WhisperModelParams(
        language="en",
        task=TaskEnum.TRANSCRIBE,
        model=WhisperModel.tiny,
        device=Device.cuda,
        device_index=0,
        threads=0,
        batch_size=8,
        chunk_size=20,
        compute_type=ComputeType.int8,
    )
    asr_options = ASROptions(
        beam_size=5,
        best_of=5,
        patience=1.0,
        length_penalty=1.0,
        compression_ratio_threshold=2.4,
        log_prob_threshold=-1.0,
        no_speech_threshold=0.6,
        initial_prompt=None,
        suppress_tokens=[-1],
        suppress_numerals=False,
        hotwords=None,
        temperatures=0.0,
    )
    return model_params, asr_options


@pytest.mark.unit
def test_gpu_semaphore_not_released_when_acquire_was_skipped(
    openai_client: tuple[TestClient, MockTranscriptionService, MockAlignmentService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If preprocessing raises before acquire, the semaphore must not be released."""
    client, _, _ = openai_client

    mock_semaphore = MagicMock()
    mock_semaphore.acquire = MagicMock()
    mock_semaphore.release = MagicMock()

    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("simulated audio decode failure")

    monkeypatch.setattr(
        "app.api.openai_compat_api.get_gpu_semaphore",
        lambda: mock_semaphore,
    )
    monkeypatch.setattr(
        "app.api.openai_compat_api.process_audio_file",
        _raise,
    )
    monkeypatch.setattr(
        "app.api.openai_compat_api.map_request_to_whisper_params",
        lambda **_kwargs: _make_cuda_whisper_params(),
    )

    # TestClient re-raises uncaught server exceptions by default; that is fine —
    # the assertions below verify that the semaphore was not released regardless
    # of which side handles the error.
    with pytest.raises(RuntimeError, match="simulated audio decode failure"):
        _post_openai_request(client)

    mock_semaphore.acquire.assert_not_called()
    mock_semaphore.release.assert_not_called()


@pytest.mark.unit
def test_openai_save_upload_failure_returns_openai_envelope(
    openai_client: tuple[TestClient, MockTranscriptionService, MockAlignmentService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An HTTPException from save_upload must surface as an OpenAI-style error."""
    client, _, _ = openai_client

    def _raise_http(*_args: Any, **_kwargs: Any) -> Any:
        raise HTTPException(status_code=400, detail="Filename is missing")

    monkeypatch.setattr(
        "app.api.openai_compat_api.FileService.save_upload",
        _raise_http,
    )

    response = _post_openai_request(client)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["type"] == "invalid_request_error"
    assert "detail" not in body


@pytest.mark.unit
def test_openai_missing_file_field_returns_openai_envelope(
    openai_client: tuple[TestClient, MockTranscriptionService, MockAlignmentService],
) -> None:
    """A request without a 'file' field returns the OpenAI-style error envelope."""
    client, _, _ = openai_client

    response = client.post(
        "/v1/audio/transcriptions",
        files=[("model", (None, "whisper-1"))],
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["type"] == "invalid_request_error"


@pytest.mark.unit
def test_openai_translation_rejects_word_timestamps(
    openai_client: tuple[TestClient, MockTranscriptionService, MockAlignmentService],
) -> None:
    """Word timestamps must be rejected on the translations endpoint."""
    client, _, _ = openai_client

    response = _post_openai_request(
        client,
        endpoint="/v1/audio/translations",
        extra_fields=[
            ("response_format", "verbose_json"),
            ("timestamp_granularities[]", "word"),
        ],
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["type"] == "invalid_request_error"


@pytest.mark.unit
def test_gpu_semaphore_released_when_acquire_succeeded(
    openai_client: tuple[TestClient, MockTranscriptionService, MockAlignmentService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the semaphore is acquired, a downstream failure must still release it."""
    client, _, _ = openai_client

    mock_semaphore = MagicMock()
    mock_semaphore.acquire = MagicMock()
    mock_semaphore.release = MagicMock()

    monkeypatch.setattr(
        "app.api.openai_compat_api.get_gpu_semaphore",
        lambda: mock_semaphore,
    )
    monkeypatch.setattr(
        "app.api.openai_compat_api.map_request_to_whisper_params",
        lambda **_kwargs: _make_cuda_whisper_params(),
    )

    response = _post_openai_request(client)

    assert response.status_code == 200
    mock_semaphore.acquire.assert_called_once()
    mock_semaphore.release.assert_called_once()


@pytest.mark.unit
def test_openai_transcription_persists_completed_task(
    openai_client_with_repo: tuple[TestClient, _FakeTaskRepository],
) -> None:
    """A successful transcription must persist a completed task with its result."""
    client, fake_repo = openai_client_with_repo

    response = _post_openai_request(
        client,
        extra_fields=[("response_format", "verbose_json")],
    )

    assert response.status_code == 200

    assert len(fake_repo.added) == 1
    added = fake_repo.added[0]
    assert added.task_type == TaskType.transcription
    assert added.status == TaskStatus.processing
    assert added.file_name == "audio_en.mp3"
    assert added.task_params is not None
    assert added.task_params["task"] == "transcribe"

    assert len(fake_repo.updates) == 1
    identifier, update = fake_repo.updates[0]
    assert identifier == added.uuid
    assert update["status"] == TaskStatus.completed
    assert update["result"]["text"] == "This is a test transcription."
    assert "segments" in update["result"]
    assert update["audio_duration"] is not None
    assert update["duration"] >= 0
    assert update["end_time"] is not None


@pytest.mark.unit
def test_openai_translation_persists_completed_task(
    openai_client_with_repo: tuple[TestClient, _FakeTaskRepository],
) -> None:
    """A successful translation must persist a completed task tagged as translate."""
    client, fake_repo = openai_client_with_repo

    response = _post_openai_request(client, endpoint="/v1/audio/translations")

    assert response.status_code == 200
    added = fake_repo.added[0]
    assert added.task_params is not None
    assert added.task_params["task"] == "translate"

    _, update = fake_repo.updates[0]
    assert update["status"] == TaskStatus.completed
    assert update["result"]["task"] == "translate"


@pytest.mark.unit
def test_openai_failed_request_persists_failed_task(
    openai_client_with_repo: tuple[TestClient, _FakeTaskRepository],
) -> None:
    """A request that fails during processing must persist a failed task."""
    client, fake_repo = openai_client_with_repo

    with open(AUDIO_FILE, "rb") as audio_file:
        response = client.post(
            "/v1/audio/transcriptions",
            files=[
                ("file", ("audio_en.mp3", audio_file, "audio/mpeg")),
                ("model", (None, "bogus-model")),
            ],
        )

    assert response.status_code == 422

    assert len(fake_repo.added) == 1
    assert len(fake_repo.updates) == 1
    identifier, update = fake_repo.updates[0]
    assert identifier == fake_repo.added[0].uuid
    assert update["status"] == TaskStatus.failed
    assert update["error"]
