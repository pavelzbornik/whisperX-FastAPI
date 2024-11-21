from fastapi.testclient import TestClient
from app import main
import time
import tempfile
import json
import pytest

client = TestClient(main.app)

import os

AUDIO_FILE = "app/tests/test_files/audio_en.mp3"
assert os.path.exists(AUDIO_FILE), f"Audio file not found: {AUDIO_FILE}"

# for tiny models a and the can be mixed
TRANSCRIPT_RESULT_1 = " This is a test audio"
TRANSCRIPT_RESULT_2 = " This is the test audio"


@pytest.fixture(autouse=True)
def set_env_variable(monkeypatch):
    monkeypatch.setenv("DB_URL", "sqlite:///:memory:")


def test_index():
    response = client.get("/", allow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def get_task_status(identifier):
    response = client.get(f"/task/{identifier}")
    if response.status_code == 200:
        return response.json()["status"]
    return None


def wait_for_task_completion(identifier, max_attempts=2, delay=10):
    attempts = 0
    while attempts < max_attempts:
        status = get_task_status(identifier)
        if status == "completed":
            return True
        if status == "failed":
            raise ValueError("Task failed")
        time.sleep(delay)
        attempts += 1
    return False


def generic_transcription(client_url):

    with open(AUDIO_FILE, "rb") as audio_file:
        files = {"file": ("audio_en.mp3", audio_file)}
        response = client.post(
            f"{client_url}",
            files=files,
        )
    assert response.status_code == 200
    assert "Task queued" in response.json()["message"]

    # Extract identifier from the response
    identifier = response.json()["identifier"]

    # Wait for the task to be completed
    assert wait_for_task_completion(
        identifier
    ), f"Task with identifier {identifier} did not complete within the expected time."

    task_result = client.get(f"/task/{identifier}")
    seg_0_text = task_result.json()["result"]["segments"][0]["text"]
    assert seg_0_text.startswith(TRANSCRIPT_RESULT_1) or seg_0_text.startswith(
        TRANSCRIPT_RESULT_2
    )

    return task_result.json()["result"]


def align(transcript_file):
    with open(transcript_file, "rb") as transcript_file, open(
        AUDIO_FILE, "rb"
    ) as audio_file:
        response = client.post(
            "/service/align",
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
    assert wait_for_task_completion(
        identifier
    ), f"Task with identifier {identifier} did not complete within the expected time."

    task_result = client.get(f"/task/{identifier}")

    return task_result.json()["result"]


def diarize():
    with open(AUDIO_FILE, "rb") as audio_file:
        files = {"file": ("audio_en.mp3", audio_file)}
        response = client.post(
            "/service/diarize",
            files=files,
        )
    assert response.status_code == 200
    assert "Task queued" in response.json()["message"]

    # Extract identifier from the response
    identifier = response.json()["identifier"]

    # Wait for the task to be completed
    assert wait_for_task_completion(
        identifier
    ), f"Task with identifier {identifier} did not complete within the expected time."

    task_result = client.get(f"/task/{identifier}")

    return task_result.json()["result"]


def combine(aligned_transcript_file, diarazition_file):

    with open(aligned_transcript_file, "rb") as transcript_file, open(
        diarazition_file, "rb"
    ) as diarization_result:
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
    assert wait_for_task_completion(
        identifier
    ), f"Task with identifier {identifier} did not complete within the expected time."

    task_result = client.get(f"/task/{identifier}")

    return task_result.json()["result"]


def test_speech_to_text():
    assert generic_transcription("/speech-to-text?language=en") is not None


def test_transcribe():
    assert generic_transcription("/service/transcribe") is not None


def test_align():

    assert align("app/tests/test_files/transcript.json") is not None


def test_diarize():

    assert diarize() is not None


def test_flow():
    # Create temporary files for transcript, aligned transcript, and diarization
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False
    ) as transcript_file, tempfile.NamedTemporaryFile(
        mode="w", delete=False
    ) as aligned_transcript_file, tempfile.NamedTemporaryFile(
        mode="w", delete=False
    ) as diarization_file:

        # Write the transcription result to the temporary transcript file
        json.dump(
            generic_transcription("/service/transcribe"), transcript_file
        )
        transcript_file.flush()  # Ensure data is written to the file

        # Write the aligned transcription result to the temporary aligned transcript file
        json.dump(align(transcript_file.name), aligned_transcript_file)
        aligned_transcript_file.flush()

        # Write the diarization result to the temporary diarization file
        json.dump(diarize(), diarization_file)
        diarization_file.flush()

        result = combine(aligned_transcript_file.name, diarization_file.name)

        assert result["segments"][0]["text"].startswith(TRANSCRIPT_RESULT_2)


def test_combine():
    result = combine(
        "app/tests/test_files/aligned_transcript.json",
        "app/tests/test_files/diarazition.json",
    )

    assert result["segments"][0]["text"].startswith(
        TRANSCRIPT_RESULT_1
    ) or result["segments"][0]["text"].startswith(TRANSCRIPT_RESULT_2)


def test_speech_to_text_url():
    # There is sometimes issue with CUDA memory better run this test individually
    response = client.post(
        "/speech-to-text-url?language=en",
        data={
            "url": "https://github.com/tijszwinkels/whisperX-api/raw/main/audio_en.mp3"
        },
    )
    assert response.status_code == 200
    assert "Task queued" in response.json()["message"]

    # Extract identifier from the response
    identifier = response.json()["identifier"]

    # Wait for the task to be completed
    assert wait_for_task_completion(
        identifier
    ), f"Task with identifier {identifier} did not complete within the expected time."

    task_result = client.get(f"/task/{identifier}")
    seg_0_text = task_result.json()["result"]["segments"][0]["text"]
    assert seg_0_text.startswith(TRANSCRIPT_RESULT_1) or seg_0_text.startswith(
        TRANSCRIPT_RESULT_2
    )


def test_get_all_tasks_status():
    response = client.get("/task/all")
    assert response.status_code == 200
    assert "tasks" in response.json()
    assert isinstance(response.json()["tasks"], list)


def test_delete_task():
    # Create a task first to delete
    with open(AUDIO_FILE, "rb") as audio_file:
        files = {"file": ("audio_en.mp3", audio_file)}
        response = client.post(
            "/service/transcribe",
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
