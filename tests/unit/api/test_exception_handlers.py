"""Tests for exception handlers."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.exception_handlers import (
    domain_error_handler,
    generic_error_handler,
    infrastructure_error_handler,
    task_not_found_handler,
    validation_error_handler,
)
from app.core.exceptions import (
    DomainError,
    InfrastructureError,
    TaskNotFoundError,
    TranscriptionFailedError,
    UnsupportedFileExtensionError,
    ValidationError,
)

# Create a test app
app = FastAPI()

# Register exception handlers
app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
app.add_exception_handler(ValidationError, validation_error_handler)
app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(InfrastructureError, infrastructure_error_handler)
app.add_exception_handler(Exception, generic_error_handler)


# Test routes
@app.get("/test/task-not-found")
async def raise_task_not_found() -> None:
    """Raise TaskNotFoundError."""
    raise TaskNotFoundError(identifier="test-123")


@app.get("/test/validation-error")
async def raise_validation_error() -> None:
    """Raise ValidationError."""
    raise ValidationError(message="Invalid input", field="email")


@app.get("/test/unsupported-file")
async def raise_unsupported_file_error() -> None:
    """Raise UnsupportedFileExtensionError."""
    raise UnsupportedFileExtensionError(
        filename="test.txt", extension=".txt", allowed={".mp3", ".wav"}
    )


@app.get("/test/domain-error")
async def raise_domain_error() -> None:
    """Raise DomainError."""
    raise DomainError(message="Business rule violated", code="BUSINESS_ERROR")


@app.get("/test/transcription-failed")
async def raise_transcription_failed() -> None:
    """Raise TranscriptionFailedError."""
    raise TranscriptionFailedError(reason="Model failed", original_error=None)


@app.get("/test/infrastructure-error")
async def raise_infrastructure_error() -> None:
    """Raise InfrastructureError."""
    raise InfrastructureError(message="Database connection failed", code="DB_ERROR")


@app.get("/test/generic-error")
async def raise_generic_error() -> None:
    """Raise generic exception."""
    raise ValueError("Unexpected error")


# Test client
client = TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
def test_task_not_found_handler() -> None:
    """Test TaskNotFoundError handler returns 404."""
    response = client.get("/test/task-not-found")

    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "TASK_NOT_FOUND"
    assert "test-123" in str(data["error"])
    assert "correlation_id" in data["error"]


@pytest.mark.unit
def test_validation_error_handler() -> None:
    """Test ValidationError handler returns 422."""
    response = client.get("/test/validation-error")

    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "correlation_id" in data["error"]


@pytest.mark.unit
def test_unsupported_file_extension_handler() -> None:
    """Test UnsupportedFileExtensionError (ValidationError subclass) returns 422."""
    response = client.get("/test/unsupported-file")

    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNSUPPORTED_FILE_EXTENSION"
    assert ".txt" in data["error"]["message"]
    assert "correlation_id" in data["error"]


@pytest.mark.unit
def test_domain_error_handler() -> None:
    """Test DomainError handler returns 400."""
    response = client.get("/test/domain-error")

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "BUSINESS_ERROR"
    assert "correlation_id" in data["error"]


@pytest.mark.unit
def test_transcription_failed_handler() -> None:
    """Test TranscriptionFailedError (DomainError subclass) returns 400."""
    response = client.get("/test/transcription-failed")

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "TRANSCRIPTION_FAILED"
    assert "correlation_id" in data["error"]


@pytest.mark.unit
def test_infrastructure_error_handler() -> None:
    """Test InfrastructureError handler returns 503."""
    response = client.get("/test/infrastructure-error")

    assert response.status_code == 503
    data = response.json()
    assert "error" in data
    # Should NOT expose internal details
    assert "Database connection failed" not in data["error"]["message"]
    # Should return generic message
    assert "temporary system error" in data["error"]["message"].lower()
    assert data["error"]["code"] == "DB_ERROR"
    assert "correlation_id" in data["error"]


@pytest.mark.unit
def test_generic_error_handler() -> None:
    """Test generic exception handler returns 500."""
    response = client.get("/test/generic-error")

    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INTERNAL_ERROR"
    # Should NOT expose internal details
    assert "Unexpected error" not in data["error"]["message"]
    # Should return generic message
    assert "unexpected error" in data["error"]["message"].lower()
    assert "correlation_id" in data["error"]


@pytest.mark.unit
def test_error_response_format() -> None:
    """Test all errors follow consistent response format."""
    endpoints = [
        "/test/task-not-found",
        "/test/validation-error",
        "/test/domain-error",
        "/test/infrastructure-error",
        "/test/generic-error",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        data = response.json()

        # All errors should have this structure
        assert "error" in data
        assert "message" in data["error"]
        assert "code" in data["error"]
        assert "correlation_id" in data["error"]

        # Correlation ID should be a valid UUID format
        correlation_id = data["error"]["correlation_id"]
        assert len(correlation_id) == 36
        assert correlation_id.count("-") == 4
