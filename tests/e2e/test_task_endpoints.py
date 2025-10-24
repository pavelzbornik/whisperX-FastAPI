"""End-to-end tests for task management endpoints."""

import os

import pytest
from fastapi.testclient import TestClient

AUDIO_FILE = "tests/test_files/audio_en.mp3"


@pytest.fixture(scope="module")
def client() -> TestClient:
    """
    Create and return test client.

    Returns:
        TestClient: The FastAPI test client instance
    """
    from app import main

    return TestClient(main.app, follow_redirects=False)


@pytest.mark.e2e
def test_get_all_tasks_status(client: TestClient) -> None:
    """Test retrieving the status of all tasks."""
    response = client.get("/task/all")
    assert response.status_code == 200
    assert "tasks" in response.json()
    assert isinstance(response.json()["tasks"], list)


@pytest.mark.e2e
def test_delete_task(client: TestClient) -> None:
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
    assert get_response.json()["error"]["code"] == "TASK_NOT_FOUND"


@pytest.mark.e2e
def test_get_task_by_id(client: TestClient) -> None:
    """Test retrieving a specific task by ID."""
    # Create a task first
    with open(AUDIO_FILE, "rb") as audio_file:
        files = {"file": ("audio_en.mp3", audio_file)}
        response = client.post(
            f"/service/transcribe?device={os.getenv('DEVICE')}&compute_type={os.getenv('COMPUTE_TYPE')}",
            files=files,
        )
    assert response.status_code == 200
    identifier = response.json()["identifier"]

    # Retrieve the task
    get_response = client.get(f"/task/{identifier}")
    assert get_response.status_code == 200
    task_data = get_response.json()
    # Verify the response has expected fields
    assert "status" in task_data
    assert task_data["status"] in ["pending", "processing", "completed", "failed"]
    assert "metadata" in task_data or "result" in task_data  # Has task data


@pytest.mark.e2e
def test_get_nonexistent_task(client: TestClient) -> None:
    """Test retrieving a non-existent task returns 404."""
    response = client.get("/task/non-existent-uuid-12345")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"
