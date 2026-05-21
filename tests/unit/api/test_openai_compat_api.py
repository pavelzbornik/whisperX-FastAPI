"""Unit tests for the OpenAI-compatible API endpoints."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient

import app.main as main_module
from tests.mocks import MockAlignmentService, MockTranscriptionService

AUDIO_FILE = "tests/test_files/audio_en.mp3"


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
