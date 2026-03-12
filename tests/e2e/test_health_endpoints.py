"""End-to-end tests for health check endpoints."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
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


@pytest.mark.e2e
def test_index_redirects_to_docs(client: TestClient) -> None:
    """Test the index route redirects to the documentation."""
    response = client.get("/")
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


@pytest.mark.e2e
def test_health_check(client: TestClient) -> None:
    """Test the basic health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["message"] == "Service is running"


@pytest.mark.e2e
def test_liveness_check(client: TestClient) -> None:
    """Test the liveness check endpoint."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert data["message"] == "Application is live"
    # Verify timestamp is a valid number
    assert isinstance(data["timestamp"], (int, float))


@pytest.mark.e2e
def test_readiness_check(client: TestClient) -> None:
    """Test the readiness check endpoint."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["message"] == "Application is ready to accept requests"


@pytest.mark.e2e
def test_readiness_check_with_db_failure(client: TestClient) -> None:
    """Test the readiness check endpoint when database connection fails."""

    # Async context manager that raises TimeoutError on enter
    class _FailingAsyncConn:
        async def __aenter__(self) -> "_FailingAsyncConn":
            raise TimeoutError("Database connection failed")

        async def __aexit__(self, *args: Any) -> None:
            """Exit the context manager."""

    mock_engine = MagicMock()
    mock_engine.connect.return_value = _FailingAsyncConn()

    with patch("app.main.async_engine", mock_engine):
        response = client.get("/health/ready")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["database"] == "disconnected"
    assert data["message"] == "Application is not ready due to an internal error."
