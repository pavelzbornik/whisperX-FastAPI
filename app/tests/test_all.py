from fastapi.testclient import TestClient
from app import main
import time


client = TestClient(main.app)

AUDIO_FILE = "test_files/audio_en.mp3"


def test_index():
    response = client.get("/", allow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def get_task_status(identifier):
    response = client.get(f"/transcription_status/{identifier}")
    if response.status_code == 200:
        return response.json()["status"]
    return None


def wait_for_task_completion(identifier, max_attempts=10, delay=10):
    attempts = 0
    while attempts < max_attempts:
        status = get_task_status(identifier)
        if status == "completed":
            return True
        time.sleep(delay)
        attempts += 1
    return False


def test_speech_to_text():
    # There is sometimes issue with CUDA memory better run this test individually
    with open(AUDIO_FILE, "rb") as audio_file:
        files = {"file": ("audio_en.mp3", audio_file)}
        response = client.post(
            "/speech-to-text?language=en",
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

    task_result = client.get(f"/transcription_status/{identifier}")
    seg_0_text = task_result.json()['result']['segments'][0]['text']
    assert seg_0_text.startswith(' This is a test audio')

def test_transcribe():
    # There is sometimes issue with CUDA memory better run this test individually

    with open(AUDIO_FILE, "rb") as audio_file:
        files = {"file": ("audio_en.mp3", audio_file)}
        response = client.post(
            "/transcribe",
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


def test_align():
    with open("test_files/transcript.json", "rb") as transcript_file, open(
        AUDIO_FILE, "rb"
    ) as audio_file:
        response = client.post(
            "/align",
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


def test_diarize():
    with open(AUDIO_FILE, "rb") as audio_file:
        files = {"file": ("audio_en.mp3", audio_file)}
        response = client.post(
            "/diarize",
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


def test_combine():
    
    with open(
        "test_files/aligned_transcript.json", "rb"
    ) as transcript_file, open(
        "test_files/diarazition.json", "rb"
    ) as diarization_result:
        files = {
            "aligned_transcript": ("aligned_transcript.json", transcript_file),
            "diarization_result": ("diarazition.json", diarization_result),
        }
        response = client.post(
            "/combine",
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
    
    task_result = client.get(f"/transcription_status/{identifier}")
    seg_0_text = task_result.json()['result']['segments'][0]['text']
    assert seg_0_text.startswith(' This is a test audio')


def test_get_all_tasks_status():
    response = client.get("/all_tasks_status")
    assert response.status_code == 200
    assert "tasks" in response.json()
    assert isinstance(response.json()["tasks"], list)
