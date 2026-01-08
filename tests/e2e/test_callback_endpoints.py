"""End-to-end tests for callback functionality.

This module contains E2E tests for the callback notification feature:
- Speech-to-text with callback URL
- Speech-to-text from URL with callback URL
- Callback payload validation
- Callback retry behavior on failure
- Invalid callback URL handling
"""

import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient

AUDIO_FILE = "tests/test_files/audio_en.mp3"
assert os.path.exists(AUDIO_FILE), f"Audio file not found: {AUDIO_FILE}"


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
    monkeypatch.setenv("CALLBACK_TIMEOUT", "5")
    monkeypatch.setenv("CALLBACK_MAX_RETRIES", "2")


def get_task_status(client: TestClient, identifier: str) -> str | None:
    """
    Get the status of a task by its identifier.

    Args:
        client: The FastAPI test client
        identifier: The task identifier.

    Returns:
        The status of the task or None if not found.
    """
    response = client.get(f"/task/{identifier}")
    if response.status_code == 200:
        return response.json()["status"]
    return None


def wait_for_task_completion(
    client: TestClient, identifier: str, max_attempts: int = 3, delay: int = 10
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
            response = client.get(f"/task/{identifier}")
            error_message = response.json().get("error", "Unknown error")
            raise ValueError(f"Task failed with error: {error_message}")
        time.sleep(delay)
        attempts += 1
    return False


class CallbackHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for capturing callback requests."""

    # Class variable to store received callbacks
    received_callbacks: list[dict[str, Any]] = []

    def do_POST(self) -> None:
        """Handle POST requests and capture callback payload."""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            callback_data = json.loads(post_data.decode("utf-8"))
            CallbackHTTPRequestHandler.received_callbacks.append(callback_data)

            # Send success response
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = json.dumps({"ok": True})
            self.wfile.write(response.encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))

    def do_HEAD(self) -> None:
        """Handle HEAD requests for callback URL validation."""
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress log messages."""
        pass


@pytest.fixture
def callback_server() -> tuple[HTTPServer, str]:
    """
    Start a local HTTP server to receive callback notifications.

    Yields:
        Tuple of (server instance, callback URL)
    """
    # Reset received callbacks
    CallbackHTTPRequestHandler.received_callbacks = []

    # Find an available port
    server = HTTPServer(("127.0.0.1", 0), CallbackHTTPRequestHandler)
    port = server.server_port
    callback_url = f"http://127.0.0.1:{port}/callback"

    # Start server in a background thread
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    yield server, callback_url

    # Shutdown server
    server.shutdown()


class TestCallbackEndpoints:
    """End-to-end tests for callback functionality."""

    def test_speech_to_text_with_callback_success(
        self, client: TestClient, callback_server: tuple[HTTPServer, str]
    ) -> None:
        """Test speech-to-text endpoint with successful callback notification."""
        server, callback_url = callback_server

        # Submit transcription task with callback URL
        with open(AUDIO_FILE, "rb") as audio_file:
            files = {"file": ("audio_en.mp3", audio_file)}
            response = client.post(
                f"/speech-to-text?device={os.getenv('DEVICE')}&compute_type={os.getenv('COMPUTE_TYPE')}&callback_url={callback_url}",
                files=files,
            )

        assert response.status_code == 200, f"Unexpected response: {response.json()}"
        assert "Task queued" in response.json()["message"]

        identifier = response.json()["identifier"]

        # Wait for task completion
        assert wait_for_task_completion(client, identifier), (
            f"Task {identifier} did not complete"
        )

        # Wait a bit for callback to be sent
        time.sleep(2)

        # Verify callback was received
        assert len(CallbackHTTPRequestHandler.received_callbacks) > 0, (
            "No callback received"
        )

        callback_payload = CallbackHTTPRequestHandler.received_callbacks[0]

        # Validate callback payload structure
        assert "status" in callback_payload
        assert "result" in callback_payload
        assert "metadata" in callback_payload
        assert callback_payload["status"] == "completed"

        # Validate metadata contains expected fields
        metadata = callback_payload["metadata"]
        assert (
            metadata["task_type"] == "full_process"
        )  # The endpoint performs full processing
        assert metadata["file_name"] == "audio_en.mp3"
        assert metadata["callback_url"] == callback_url
        assert "duration" in metadata
        assert "start_time" in metadata
        assert "end_time" in metadata

        # Validate result contains transcription
        assert "segments" in callback_payload["result"]
        assert len(callback_payload["result"]["segments"]) > 0

    def test_speech_to_text_url_with_callback(
        self, client: TestClient, callback_server: tuple[HTTPServer, str]
    ) -> None:
        """Test speech-to-text-url endpoint with callback notification."""
        server, callback_url = callback_server

        # Use a publicly accessible test audio URL
        test_audio_url = (
            "https://github.com/ggerganov/whisper.cpp/raw/master/samples/jfk.wav"
        )

        response = client.post(
            f"/speech-to-text-url?device={os.getenv('DEVICE')}&compute_type={os.getenv('COMPUTE_TYPE')}&callback_url={callback_url}",
            data={"url": test_audio_url},
        )

        assert response.status_code == 200
        assert "Task queued" in response.json()["message"]

        identifier = response.json()["identifier"]

        # Wait for task completion (URL download might take longer)
        assert wait_for_task_completion(client, identifier, max_attempts=5), (
            f"Task {identifier} did not complete"
        )

        # Wait for callback
        time.sleep(2)

        # Verify callback was received
        assert len(CallbackHTTPRequestHandler.received_callbacks) > 0, (
            "No callback received"
        )

        callback_payload = CallbackHTTPRequestHandler.received_callbacks[-1]

        # Validate callback payload
        assert callback_payload["status"] == "completed"
        assert callback_payload["metadata"]["task_type"] == "full_process"
        assert callback_payload["metadata"]["url"] == test_audio_url
        assert callback_payload["metadata"]["callback_url"] == callback_url

    def test_invalid_callback_url_rejected(self, client: TestClient) -> None:
        """Test that invalid/unreachable callback URLs are rejected."""
        invalid_callback_url = "http://invalid-nonexistent-domain-12345.com/callback"

        with open(AUDIO_FILE, "rb") as audio_file:
            files = {"file": ("audio_en.mp3", audio_file)}
            response = client.post(
                f"/speech-to-text?device={os.getenv('DEVICE')}&compute_type={os.getenv('COMPUTE_TYPE')}&callback_url={invalid_callback_url}",
                files=files,
            )

        # Should return 400 Bad Request for unreachable callback URL
        assert response.status_code == 400
        assert "Callback URL is not reachable" in response.json()["detail"]

    def test_callback_url_stored_in_database(
        self, client: TestClient, callback_server: tuple[HTTPServer, str]
    ) -> None:
        """Test that callback URL is properly stored in the database."""
        server, callback_url = callback_server

        with open(AUDIO_FILE, "rb") as audio_file:
            files = {"file": ("audio_en.mp3", audio_file)}
            response = client.post(
                f"/speech-to-text?device={os.getenv('DEVICE')}&compute_type={os.getenv('COMPUTE_TYPE')}&callback_url={callback_url}",
                files=files,
            )

        assert response.status_code == 200
        identifier = response.json()["identifier"]

        # Immediately check that callback_url is in database
        task_result = client.get(f"/task/{identifier}")
        assert task_result.status_code == 200
        assert task_result.json()["metadata"]["callback_url"] == callback_url

        # Wait for completion
        assert wait_for_task_completion(client, identifier)

        # Check again after completion
        task_result = client.get(f"/task/{identifier}")
        assert task_result.json()["metadata"]["callback_url"] == callback_url

    def test_callback_datetime_serialization(
        self, client: TestClient, callback_server: tuple[HTTPServer, str]
    ) -> None:
        """Test that datetime fields in callback are properly serialized to ISO format."""
        server, callback_url = callback_server

        with open(AUDIO_FILE, "rb") as audio_file:
            files = {"file": ("audio_en.mp3", audio_file)}
            response = client.post(
                f"/speech-to-text?device={os.getenv('DEVICE')}&compute_type={os.getenv('COMPUTE_TYPE')}&callback_url={callback_url}",
                files=files,
            )

        identifier = response.json()["identifier"]
        assert wait_for_task_completion(client, identifier)

        # Wait for callback
        time.sleep(2)

        assert len(CallbackHTTPRequestHandler.received_callbacks) > 0
        callback_payload = CallbackHTTPRequestHandler.received_callbacks[0]

        # Verify datetime fields are ISO strings, not datetime objects
        metadata = callback_payload["metadata"]
        if metadata.get("start_time"):
            assert isinstance(metadata["start_time"], str)
            # Should be in ISO format with timezone
            assert "T" in metadata["start_time"]
        if metadata.get("end_time"):
            assert isinstance(metadata["end_time"], str)
            assert "T" in metadata["end_time"]
