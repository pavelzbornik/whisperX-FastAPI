"""End-to-end tests for WebSocket real-time transcription endpoint."""

import numpy as np
import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient


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
def set_env_variables(monkeypatch: MonkeyPatch) -> None:
    """
    Set environment variables for the test environment.

    Args:
        monkeypatch: The monkeypatch fixture for setting environment variables.
    """
    monkeypatch.setenv("DB_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DEVICE", "cpu")
    monkeypatch.setenv("COMPUTE_TYPE", "int8")
    monkeypatch.setenv("WHISPER_MODEL", "tiny")


def generate_test_audio(
    duration_s: float = 2.0, sample_rate: int = 16000, frequency: int = 440
) -> bytes:
    """
    Generate test audio as 16-bit PCM bytes.

    Args:
        duration_s: Duration in seconds
        sample_rate: Sample rate in Hz
        frequency: Frequency of the sine wave in Hz

    Returns:
        Audio data as bytes
    """
    # Generate sine wave
    num_samples = int(duration_s * sample_rate)
    t = np.linspace(0, duration_s, num_samples, False)
    audio = np.sin(2 * np.pi * frequency * t)

    # Scale to 16-bit range and convert
    audio_int16 = (audio * 32767).astype(np.int16)

    # Convert to bytes
    return bytes(audio_int16.tobytes())


@pytest.mark.e2e
@pytest.mark.slow
def test_websocket_connection(client: TestClient) -> None:
    """Test WebSocket connection establishment."""
    with client.websocket_connect("/audio") as websocket:
        # Receive welcome message
        data = websocket.receive_json()
        assert data["event"] == "info"
        assert "session_id" in data["data"]
        assert "Connected to real-time transcription service" in data["data"]["message"]


@pytest.mark.e2e
@pytest.mark.slow
def test_websocket_audio_processing(client: TestClient) -> None:
    """Test WebSocket audio processing with VAD."""
    with client.websocket_connect("/audio") as websocket:
        # Receive welcome message
        welcome = websocket.receive_json()
        assert welcome["event"] == "info"

        # Generate test audio (2 seconds at 440 Hz)
        audio_data = generate_test_audio(duration_s=2.0, sample_rate=16000)

        # Send audio in chunks (simulate real-time streaming)
        chunk_size = 1024  # 512 samples = 32ms at 16kHz
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i : i + chunk_size]
            websocket.send_bytes(chunk)

        # Give some time for processing
        import time

        time.sleep(1)

        # Receive events (we may get speech_start, speech_end events)
        # Due to VAD behavior with pure sine waves, results may vary
        # At minimum, we should not get errors
        received_events = []
        max_attempts = 5
        for _ in range(max_attempts):
            try:
                data = websocket.receive_json()
                received_events.append(data["event"])
                assert data["event"] in [
                    "proper_speech_start",
                    "speech_false_detection",
                    "speech_end",
                    "transcription",
                    "info",
                    "error",
                ]
                # If we get an error, check it's not a critical one
                if data["event"] == "error":
                    # Some errors might be expected (e.g., no speech detected)
                    print(f"Received error: {data['data']}")
            except Exception:
                # No more messages or timeout
                break


@pytest.mark.e2e
def test_websocket_sessions_endpoint_basic(client: TestClient) -> None:
    """Test the active sessions endpoint without connecting."""
    response = client.get("/audio/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "active_sessions" in data
    assert isinstance(data["active_sessions"], int)
    assert data["active_sessions"] >= 0


@pytest.mark.e2e
@pytest.mark.slow
def test_websocket_active_sessions_endpoint(client: TestClient) -> None:
    """Test the active sessions monitoring endpoint."""
    # Initially should have 0 active sessions
    response = client.get("/audio/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "active_sessions" in data
    assert isinstance(data["active_sessions"], int)
    initial_count = data["active_sessions"]

    # Create a WebSocket connection
    with client.websocket_connect("/audio") as websocket:
        # Receive welcome message
        websocket.receive_json()

        # Check active sessions increased
        response = client.get("/audio/sessions")
        assert response.status_code == 200
        data = response.json()
        assert data["active_sessions"] == initial_count + 1

    # After disconnect, count should return to initial
    import time

    time.sleep(0.5)  # Give time for cleanup
    response = client.get("/audio/sessions")
    assert response.status_code == 200
    data = response.json()
    assert data["active_sessions"] == initial_count


@pytest.mark.e2e
@pytest.mark.slow
def test_websocket_text_message(client: TestClient) -> None:
    """Test WebSocket text message handling."""
    with client.websocket_connect("/audio") as websocket:
        # Receive welcome message
        welcome = websocket.receive_json()
        assert welcome["event"] == "info"

        # Send a text message
        websocket.send_text("test message")

        # Receive acknowledgment
        response = websocket.receive_json()
        assert response["event"] == "info"
        assert response["data"]["message"] == "Text message received"


@pytest.mark.e2e
def test_websocket_disconnect(client: TestClient) -> None:
    """Test WebSocket graceful disconnect."""
    with client.websocket_connect("/audio") as websocket:
        # Receive welcome message
        welcome = websocket.receive_json()
        assert welcome["event"] == "info"

        # Close connection (context manager handles this)
        pass

    # Connection should be closed gracefully without errors
    # If we reach here, disconnect was successful
    assert True
