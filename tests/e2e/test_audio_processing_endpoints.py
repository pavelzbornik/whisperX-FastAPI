"""End-to-end tests for audio processing endpoints.

This module contains E2E tests for the main audio processing workflows:
- Speech-to-text transcription
- Audio alignment
- Speaker diarization
- Transcript combination
- Complete audio processing flow
"""

import json
import os
import tempfile
import time
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient

AUDIO_FILE = "tests/test_files/audio_en.mp3"
assert os.path.exists(AUDIO_FILE), f"Audio file not found: {AUDIO_FILE}"

# for tiny models "a" and "the" can be mixed
TRANSCRIPT_RESULT_1 = " This is a test audio"
TRANSCRIPT_RESULT_2 = " This is the test audio"


@pytest.fixture(scope="module")
def client() -> TestClient:
    """
    Create and return test client.

    Returns:
        TestClient: The FastAPI test client instance
    """
    from app import main

    return TestClient(main.app, follow_redirects=False)


@pytest.fixture(autouse=True)
def set_env_variable(monkeypatch: MonkeyPatch) -> None:
    """
    Set environment variables for the test environment.

    Args:
        monkeypatch: The monkeypatch fixture for setting environment variables.
    """
    monkeypatch.setenv("DB_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DEVICE", "cpu")
    monkeypatch.setenv("COMPUTE_TYPE", "int8")
    monkeypatch.setenv("WHISPER_MODEL", "tiny")


def get_task_status(client: TestClient, identifier: str) -> str | None:
    """
    Get the status of a task by its identifier.

    Args:
        client: The FastAPI test client
        identifier: The task identifier.

    Returns:
        The status of the task or None if not found.
    """
    response = client.get(f"/api/v1/task/{identifier}")
    if response.status_code == 200:
        return response.json()["status"]
    return None


def wait_for_task_completion(
    client: TestClient, identifier: str, max_attempts: int = 2, delay: int = 10
) -> bool:
    """
    Wait for a task to complete by polling its status.

    Args:
        client: The FastAPI test client
        identifier: The task identifier.
        max_attempts: Maximum number of polling attempts.
        delay: Delay between polling attempts in seconds.

    Returns:
        True if the task completed, False otherwise.
    """
    from app.schemas import TaskStatus

    attempts = 0
    while attempts < max_attempts:
        status = get_task_status(client, identifier)
        if status == TaskStatus.completed:
            return True
        if status == TaskStatus.failed:
            response = client.get(f"/api/v1/task/{identifier}")
            error_message = response.json().get("error", "Unknown error")
            raise ValueError(f"Task failed with error: {error_message}")
        time.sleep(delay)
        attempts += 1
    return False


def generic_transcription(client: TestClient, client_url: str) -> dict[str, Any]:
    """
    Perform a generic transcription task and validate the result.

    Args:
        client: The FastAPI test client
        client_url: The URL endpoint for the transcription service.

    Returns:
        The result of the transcription task.
    """
    with open(AUDIO_FILE, "rb") as audio_file:
        files = {"file": ("audio_en.mp3", audio_file)}
        response = client.post(
            f"{client_url}?device={os.getenv('DEVICE')}&compute_type={os.getenv('COMPUTE_TYPE')}",
            files=files,
        )
    assert response.status_code == 200
    assert "Task queued" in response.json()["message"]

    # Extract identifier from the response
    identifier = response.json()["identifier"]

    # Wait for the task to be completed
    assert wait_for_task_completion(client, identifier), (
        f"Task with identifier {identifier} did not complete within the expected time."
    )

    task_result = client.get(f"/api/v1/task/{identifier}")
    seg_0_text = task_result.json()["result"]["segments"][0]["text"]
    assert seg_0_text.lower().startswith(
        TRANSCRIPT_RESULT_1.lower()
    ) or seg_0_text.lower().startswith(TRANSCRIPT_RESULT_2.lower())

    return task_result.json()["result"]


def align(client: TestClient, transcript_file: str) -> dict[str, Any]:
    """
    Perform an alignment task using a transcript file and validate the result.

    Args:
        client: The FastAPI test client
        transcript_file: The path to the transcript file.

    Returns:
        The result of the alignment task.
    """
    with (
        open(transcript_file, "rb") as transcript_fp,
        open(AUDIO_FILE, "rb") as audio_file,
    ):
        response = client.post(
            f"/api/v1/service/align?device={os.getenv('DEVICE')}",
            files={
                "transcript": ("transcript.json", transcript_fp),
                "file": ("audio_file.mp3", audio_file),
            },
        )

    assert response.status_code == 200
    assert "Task queued" in response.json()["message"]

    # Extract identifier from the response
    identifier = response.json()["identifier"]

    # Wait for the task to be completed
    assert wait_for_task_completion(client, identifier), (
        f"Task with identifier {identifier} did not complete within the expected time."
    )

    task_result = client.get(f"/api/v1/task/{identifier}")

    return task_result.json()["result"]


def diarize(client: TestClient) -> list[dict[str, Any]]:
    """
    Perform a diarization task and validate the result.

    Args:
        client: The FastAPI test client

    Returns:
        The result of the diarization task.
    """
    with open(AUDIO_FILE, "rb") as audio_file:
        files = {"file": ("audio_en.mp3", audio_file)}
        response = client.post(
            f"/api/v1/service/diarize?device={os.getenv('DEVICE')}",
            files=files,
        )
    assert response.status_code == 200
    assert "Task queued" in response.json()["message"]

    # Extract identifier from the response
    identifier = response.json()["identifier"]

    # Wait for the task to be completed
    assert wait_for_task_completion(client, identifier), (
        f"Task with identifier {identifier} did not complete within the expected time."
    )

    task_result = client.get(f"/api/v1/task/{identifier}")

    return task_result.json()["result"]


def combine(
    client: TestClient, aligned_transcript_file: str, diarization_file: str
) -> dict[str, Any]:
    """
    Combine aligned transcript and diarization results and validate the result.

    Args:
        client: The FastAPI test client
        aligned_transcript_file: The path to the aligned transcript file.
        diarization_file: The path to the diarization result file.

    Returns:
        The combined result.
    """
    with (
        open(aligned_transcript_file, "rb") as transcript_file,
        open(diarization_file, "rb") as diarization_result,
    ):
        files = {
            "aligned_transcript": ("aligned_transcript.json", transcript_file),
            "diarization_result": ("diarization.json", diarization_result),
        }
        response = client.post(
            "/api/v1/service/combine",
            files=files,
        )
    assert response.status_code == 200
    assert "Task queued" in response.json()["message"]

    # Extract identifier from the response
    identifier = response.json()["identifier"]

    # Wait for the task to be completed
    assert wait_for_task_completion(client, identifier), (
        f"Task with identifier {identifier} did not complete within the expected time."
    )

    task_result = client.get(f"/api/v1/task/{identifier}")

    return task_result.json()["result"]


@pytest.mark.e2e
@pytest.mark.slow
def test_speech_to_text(client: TestClient) -> None:
    """Test the speech-to-text service end-to-end."""
    result = generic_transcription(client, "/api/v1/speech-to-text")
    assert result is not None
    assert "segments" in result
    assert len(result["segments"]) > 0


@pytest.mark.e2e
@pytest.mark.slow
def test_transcribe_service(client: TestClient) -> None:
    """Test the transcription service endpoint."""
    result = generic_transcription(client, "/api/v1/service/transcribe")
    assert result is not None
    assert "segments" in result
    assert len(result["segments"]) > 0


@pytest.mark.e2e
@pytest.mark.slow
def test_align_service(client: TestClient) -> None:
    """Test the alignment service endpoint."""
    result = align(client, "tests/test_files/transcript.json")
    assert result is not None
    assert "segments" in result


@pytest.mark.e2e
@pytest.mark.slow
def test_diarize_service(client: TestClient) -> None:
    """Test the diarization service endpoint."""
    result = diarize(client)
    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 0


@pytest.mark.e2e
@pytest.mark.slow
def test_combine_service(client: TestClient) -> None:
    """Test the combination service endpoint."""
    result = combine(
        client,
        "tests/test_files/aligned_transcript.json",
        "tests/test_files/diarazition.json",
    )
    assert result is not None
    assert "segments" in result
    assert result["segments"][0]["text"].lower().startswith(
        TRANSCRIPT_RESULT_1.lower()
    ) or result["segments"][0]["text"].lower().startswith(TRANSCRIPT_RESULT_2.lower())


@pytest.mark.e2e
@pytest.mark.slow
def test_speech_to_text_url(client: TestClient) -> None:
    """Test the speech-to-text service with a URL input."""
    response = client.post(
        f"/api/v1/speech-to-text-url?device={os.getenv('DEVICE')}&compute_type={os.getenv('COMPUTE_TYPE')}",
        data={
            "url": "https://github.com/tijszwinkels/whisperX-api/raw/main/audio_en.mp3"
        },
    )
    assert response.status_code == 200
    assert "Task queued" in response.json()["message"]

    # Extract identifier from the response
    identifier = response.json()["identifier"]

    # Wait for the task to be completed
    assert wait_for_task_completion(client, identifier), (
        f"Task with identifier {identifier} did not complete within the expected time."
    )

    task_result = client.get(f"/api/v1/task/{identifier}")
    seg_0_text = task_result.json()["result"]["segments"][0]["text"]
    assert seg_0_text.lower().startswith(
        TRANSCRIPT_RESULT_1.lower()
    ) or seg_0_text.lower().startswith(TRANSCRIPT_RESULT_2.lower())


@pytest.mark.e2e
@pytest.mark.slow
def test_complete_audio_processing_flow(client: TestClient) -> None:
    """Test the complete flow: transcription, alignment, diarization, and combination."""
    # Create temporary files for transcript, aligned transcript, and diarization
    with (
        tempfile.NamedTemporaryFile(mode="w", delete=False) as transcript_file,
        tempfile.NamedTemporaryFile(mode="w", delete=False) as aligned_transcript_file,
        tempfile.NamedTemporaryFile(mode="w", delete=False) as diarization_file,
    ):
        # Step 1: Transcribe audio
        transcription_result = generic_transcription(
            client, "/api/v1/service/transcribe"
        )
        json.dump(transcription_result, transcript_file)
        transcript_file.flush()

        # Step 2: Align transcript with audio
        alignment_result = align(client, transcript_file.name)
        json.dump(alignment_result, aligned_transcript_file)
        aligned_transcript_file.flush()

        # Step 3: Diarize audio
        diarization_result = diarize(client)
        json.dump(diarization_result, diarization_file)
        diarization_file.flush()

        # Step 4: Combine results
        combined_result = combine(
            client, aligned_transcript_file.name, diarization_file.name
        )

        # Verify the final result
        assert combined_result is not None
        assert "segments" in combined_result
        assert len(combined_result["segments"]) > 0
        assert combined_result["segments"][0]["text"].lower().startswith(
            TRANSCRIPT_RESULT_1.lower()
        ) or combined_result["segments"][0]["text"].lower().startswith(
            TRANSCRIPT_RESULT_2.lower()
        )
