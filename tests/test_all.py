"""This module contains tests for the FastAPI application."""

import json
import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

from app import main
from app.db import engine

client = TestClient(main.app, follow_redirects=False)


AUDIO_FILE = "tests/test_files/audio_en.mp3"
assert os.path.exists(AUDIO_FILE), f"Audio file not found: {AUDIO_FILE}"

# for tiny models a and the can be mixed
TRANSCRIPT_RESULT_1 = " This is a test audio"
TRANSCRIPT_RESULT_2 = " This is the test audio"


@pytest.fixture(autouse=True)
def set_env_variable(monkeypatch):
    """
    Set environment variables for the test environment.

    Args:
        monkeypatch (pytest.MonkeyPatch): The monkeypatch fixture for setting environment variables.
    """
    monkeypatch.setenv("DB_URL", "sqlite:///:memory:")
    # monkeypatch.setenv("DEVICE", "cpu")
    # monkeypatch.setenv("COMPUTE_TYPE", "int8")


def test_index():
    """Test the index route to ensure it redirects to the documentation."""
    response = client.get("/")
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


# Health check tests
def test_health_check():
    """Test the basic health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["message"] == "Service is running"


def test_liveness_check():
    """Test the liveness check endpoint."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert data["message"] == "Application is live"
    # Verify timestamp is a valid number
    assert isinstance(data["timestamp"], (int, float))


def test_readiness_check():
    """Test the readiness check endpoint."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["message"] == "Application is ready to accept requests"


def test_readiness_check_with_db_failure(monkeypatch):
    """Test the readiness check endpoint when database connection fails."""

    # Create a mock engine connect method that raises an exception
    def mock_connect(*args, **kwargs):
        class MockConnection:
            def __enter__(self):
                raise Exception("Database connection failed")

            def __exit__(self, *args):
                pass

        return MockConnection()

    # Patch the engine.connect method
    original_connect = engine.connect
    monkeypatch.setattr(engine, "connect", mock_connect)

    try:
        response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "error"
        assert data["database"] == "disconnected"
        assert "Database connection failed" in data["message"]
    finally:
        # Restore the original connect method
        monkeypatch.setattr(engine, "connect", original_connect)


def get_task_status(identifier):
    """
    Get the status of a task by its identifier.

    Args:
        identifier (str): The task identifier.

    Returns:
        str: The status of the task or None if not found.
    """
    response = client.get(f"/task/{identifier}")
    if response.status_code == 200:
        return response.json()["status"]
    return None


def wait_for_task_completion(identifier, max_attempts=2, delay=10):
    """
    Wait for a task to complete by polling its status.

    Args:
        identifier (str): The task identifier.
        max_attempts (int): Maximum number of polling attempts.
        delay (int): Delay between polling attempts in seconds.

    Returns:
        bool: True if the task completed, False otherwise.
    """
    attempts = 0
    while attempts < max_attempts:
        status = get_task_status(identifier)
        if status == "completed":
            return True
        if status == "failed":
            response = client.get(f"/task/{identifier}")
            error_message = response.json().get("error", "Unknown error")
            raise ValueError(f"Task failed with error: {error_message}")
        time.sleep(delay)
        attempts += 1
    return False


def generic_transcription(client_url):
    """
    Perform a generic transcription task and validate the result.

    Args:
        client_url (str): The URL endpoint for the transcription service.

    Returns:
        dict: The result of the transcription task.
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
    assert wait_for_task_completion(identifier), (
        f"Task with identifier {identifier} did not complete within the expected time."
    )

    task_result = client.get(f"/task/{identifier}")
    seg_0_text = task_result.json()["result"]["segments"][0]["text"]
    assert seg_0_text.lower().startswith(
        TRANSCRIPT_RESULT_1.lower()
    ) or seg_0_text.lower().startswith(TRANSCRIPT_RESULT_2.lower())

    return task_result.json()["result"]


def align(transcript_file):
    """
    Perform an alignment task using a transcript file and validate the result.

    Args:
        transcript_file (str): The path to the transcript file.

    Returns:
        dict: The result of the alignment task.
    """
    with (
        open(transcript_file, "rb") as transcript_file,
        open(AUDIO_FILE, "rb") as audio_file,
    ):
        response = client.post(
            f"/service/align?device={os.getenv('DEVICE')}",
            files={
                "transcript": ("transcript.json", transcript_file),
                "file": ("audio_file.mp3", audio_file),
            },
        )

    assert response.status_code == 200
    assert "Task queued" in response.json()["message"]

    # Extract identifier from the response
    identifier = response.json()["identifier"]

    # Wait for the task to be completed
    assert wait_for_task_completion(identifier), (
        f"Task with identifier {identifier} did not complete within the expected time."
    )

    task_result = client.get(f"/task/{identifier}")

    return task_result.json()["result"]


def diarize():
    """
    Perform a diarization task and validate the result.

    Returns:
        dict: The result of the diarization task.
    """
    with open(AUDIO_FILE, "rb") as audio_file:
        files = {"file": ("audio_en.mp3", audio_file)}
        response = client.post(
            f"/service/diarize?device={os.getenv('DEVICE')}",
            files=files,
        )
    assert response.status_code == 200
    assert "Task queued" in response.json()["message"]

    # Extract identifier from the response
    identifier = response.json()["identifier"]

    # Wait for the task to be completed
    assert wait_for_task_completion(identifier), (
        f"Task with identifier {identifier} did not complete within the expected time."
    )

    task_result = client.get(f"/task/{identifier}")

    return task_result.json()["result"]


def combine(aligned_transcript_file, diarazition_file):
    """
    Combine aligned transcript and diarization results and validate the result.

    Args:
        aligned_transcript_file (str): The path to the aligned transcript file.
        diarazition_file (str): The path to the diarization result file.

    Returns:
        dict: The combined result.
    """
    with (
        open(aligned_transcript_file, "rb") as transcript_file,
        open(diarazition_file, "rb") as diarization_result,
    ):
        files = {
            "aligned_transcript": ("aligned_transcript.json", transcript_file),
            "diarization_result": ("diarazition.json", diarization_result),
        }
        response = client.post(
            "/service/combine",
            files=files,
        )
    print(response.json())
    assert response.status_code == 200
    assert "Task queued" in response.json()["message"]

    # Extract identifier from the response
    identifier = response.json()["identifier"]

    # Wait for the task to be completed
    assert wait_for_task_completion(identifier), (
        f"Task with identifier {identifier} did not complete within the expected time."
    )

    task_result = client.get(f"/task/{identifier}")

    return task_result.json()["result"]


# @pytest.mark.skipif(os.getenv("DEVICE") == "cpu", reason="Test requires GPU")
def test_speech_to_text():
    """Test the speech-to-text service."""
    assert generic_transcription("/speech-to-text") is not None


def test_transcribe():
    """Test the transcription service."""
    assert generic_transcription("/service/transcribe") is not None


def test_align():
    """Test the alignment service."""
    assert align("tests/test_files/transcript.json") is not None


# @pytest.mark.skipif(os.getenv("DEVICE") == "cpu", reason="Test requires GPU")
def test_diarize():
    """Test the diarization service."""
    assert diarize() is not None


# @pytest.mark.skipif(os.getenv("DEVICE") == "cpu", reason="Test requires GPU")
def test_flow():
    """Test the complete flow of transcription, alignment, diarization, and combination."""
    # Create temporary files for transcript, aligned transcript, and diarization
    with (
        tempfile.NamedTemporaryFile(mode="w", delete=False) as transcript_file,
        tempfile.NamedTemporaryFile(mode="w", delete=False) as aligned_transcript_file,
        tempfile.NamedTemporaryFile(mode="w", delete=False) as diarization_file,
    ):
        # Write the transcription result to the temporary transcript file
        json.dump(generic_transcription("/service/transcribe"), transcript_file)
        transcript_file.flush()  # Ensure data is written to the file

        # Write the aligned transcription result to the temporary aligned transcript file
        json.dump(align(transcript_file.name), aligned_transcript_file)
        aligned_transcript_file.flush()

        # Write the diarization result to the temporary diarization file
        json.dump(diarize(), diarization_file)
        diarization_file.flush()

        result = combine(aligned_transcript_file.name, diarization_file.name)
        assert result["segments"][0]["text"].lower().startswith(
            TRANSCRIPT_RESULT_1.lower()
        ) or result["segments"][0]["text"].lower().startswith(
            TRANSCRIPT_RESULT_2.lower()
        )
        # assert result["segments"][0]["text"].startswith(TRANSCRIPT_RESULT_2)


def test_combine():
    """Test the combination service."""
    result = combine(
        "tests/test_files/aligned_transcript.json",
        "tests/test_files/diarazition.json",
    )

    # assert result["segments"][0]["text"].startswith(TRANSCRIPT_RESULT_1) or result[
    #     "segments"
    # ][0]["text"].startswith(TRANSCRIPT_RESULT_2)
    assert result["segments"][0]["text"].lower().startswith(
        TRANSCRIPT_RESULT_1.lower()
    ) or result["segments"][0]["text"].lower().startswith(TRANSCRIPT_RESULT_2.lower())


# @pytest.mark.skipif(os.getenv("DEVICE") == "cpu", reason="Test requires GPU")
def test_speech_to_text_url():
    """Test the speech-to-text service with a URL input."""
    # There is sometimes issue with CUDA memory better run this test individually
    response = client.post(
        f"/speech-to-text-url?device={os.getenv('DEVICE')}&compute_type={os.getenv('COMPUTE_TYPE')}",
        data={
            "url": "https://github.com/tijszwinkels/whisperX-api/raw/main/audio_en.mp3"
        },
    )
    assert response.status_code == 200
    assert "Task queued" in response.json()["message"]

    # Extract identifier from the response
    identifier = response.json()["identifier"]

    # Wait for the task to be completed
    assert wait_for_task_completion(identifier), (
        f"Task with identifier {identifier} did not complete within the expected time."
    )

    task_result = client.get(f"/task/{identifier}")
    seg_0_text = task_result.json()["result"]["segments"][0]["text"]
    assert seg_0_text.lower().startswith(
        TRANSCRIPT_RESULT_1.lower()
    ) or seg_0_text.lower().startswith(TRANSCRIPT_RESULT_2.lower())


def test_get_all_tasks_status():
    """Test retrieving the status of all tasks."""
    response = client.get("/task/all")
    assert response.status_code == 200
    assert "tasks" in response.json()
    assert isinstance(response.json()["tasks"], list)


def test_delete_task():
    """Test deleting a task."""
    # Create a task first to delete
    with open(AUDIO_FILE, "rb") as audio_file:
        files = {"file": ("audio_en.mp3", audio_file)}
        response = client.post(
            f"/service/transcribe?device={os.getenv('DEVICE')}&compute_type={os.getenv('COMPUTE_TYPE')}",
            files=files,
        )
    assert response.status_code == 200
    assert "Task queued" in response.json()["message"]

    # Extract identifier from the response
    identifier = response.json()["identifier"]

    # Attempt to delete the task
    delete_response = client.delete(f"/task/{identifier}/delete")
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Task deleted"

    # Ensure the task is not found after deletion
    get_response = client.get(f"/task/{identifier}")
    assert get_response.status_code == 404
    assert get_response.json()["detail"] == "Identifier not found"
