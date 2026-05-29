"""End-to-end tests for the OpenAI-compatible audio endpoints."""

import os

import pytest
from fastapi.testclient import TestClient

openai = pytest.importorskip("openai")

AUDIO_FILE = "tests/test_files/audio_en.mp3"


@pytest.mark.e2e
@pytest.mark.slow
def test_openai_sdk_transcription(client: TestClient) -> None:
    """The official OpenAI SDK should work against the compatibility endpoint."""
    if not os.path.exists(AUDIO_FILE):
        pytest.skip(f"Audio fixture not available: {AUDIO_FILE}")

    sdk_client = openai.OpenAI(
        api_key="test-key",
        base_url="http://testserver/v1",
        http_client=client,
    )

    with open(AUDIO_FILE, "rb") as audio_file:
        transcription = sdk_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )

    assert "this is" in transcription.text.lower()
