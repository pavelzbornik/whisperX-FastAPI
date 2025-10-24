"""Tests for core exceptions module."""

import uuid

import pytest

from app.core.exceptions import (
    AlignmentFailedError,
    ApplicationError,
    AudioProcessingError,
    AudioTooLargeError,
    AudioTooShortError,
    ConfigurationError,
    DatabaseOperationError,
    DiarizationFailedError,
    DomainError,
    FileDownloadError,
    FileValidationError,
    InfrastructureError,
    InsufficientMemoryError,
    InvalidAudioFormatError,
    InvalidTaskStateError,
    MissingConfigurationError,
    ModelLoadError,
    TaskAlreadyCompletedError,
    TaskAlreadyFailedError,
    TaskNotFoundError,
    TranscriptionFailedError,
    UnsupportedFileExtensionError,
    ValidationError,
)


@pytest.mark.unit
def test_application_error_base() -> None:
    """Test ApplicationError base class."""
    exc = ApplicationError(
        message="Test error",
        code="TEST_ERROR",
        user_message="User-friendly message",
        detail="Additional detail",
    )

    assert exc.message == "Test error"
    assert exc.code == "TEST_ERROR"
    assert exc.user_message == "User-friendly message"
    assert exc.details["detail"] == "Additional detail"
    assert exc.correlation_id is not None
    assert len(exc.correlation_id) == 36  # UUID format

    # Test to_dict
    error_dict = exc.to_dict()
    assert error_dict["error"]["message"] == "User-friendly message"
    assert error_dict["error"]["code"] == "TEST_ERROR"
    assert error_dict["error"]["correlation_id"] == exc.correlation_id
    assert error_dict["error"]["detail"] == "Additional detail"


@pytest.mark.unit
def test_application_error_default_user_message() -> None:
    """Test ApplicationError defaults user_message to message."""
    exc = ApplicationError(message="Test error", code="TEST_ERROR")

    assert exc.user_message == "Test error"


@pytest.mark.unit
def test_application_error_custom_correlation_id() -> None:
    """Test ApplicationError with custom correlation_id."""
    custom_id = str(uuid.uuid4())
    exc = ApplicationError(message="Test error", correlation_id=custom_id)

    assert exc.correlation_id == custom_id


@pytest.mark.unit
def test_domain_error() -> None:
    """Test DomainError inherits from ApplicationError."""
    exc = DomainError(message="Domain error", code="DOMAIN_TEST")

    assert isinstance(exc, ApplicationError)
    assert exc.message == "Domain error"
    assert exc.code == "DOMAIN_TEST"


@pytest.mark.unit
def test_validation_error() -> None:
    """Test ValidationError inherits from DomainError."""
    exc = ValidationError(
        message="Validation failed", code="VALIDATION_TEST", field="email"
    )

    assert isinstance(exc, DomainError)
    assert isinstance(exc, ApplicationError)
    assert exc.message == "Validation failed"
    assert exc.code == "VALIDATION_TEST"
    assert exc.details["field"] == "email"


@pytest.mark.unit
def test_infrastructure_error() -> None:
    """Test InfrastructureError inherits from ApplicationError."""
    exc = InfrastructureError(message="Infrastructure failure", code="INFRA_TEST")

    assert isinstance(exc, ApplicationError)
    assert exc.message == "Infrastructure failure"
    assert exc.code == "INFRA_TEST"


@pytest.mark.unit
def test_configuration_error() -> None:
    """Test ConfigurationError inherits from ApplicationError."""
    exc = ConfigurationError(message="Config error", code="CONFIG_TEST")

    assert isinstance(exc, ApplicationError)
    assert exc.message == "Config error"
    assert exc.code == "CONFIG_TEST"


@pytest.mark.unit
<<<<<<< HEAD
def test_database_operation_error() -> None:
    """Test DatabaseOperationError."""
    original_error = Exception("Connection timeout")
    exc = DatabaseOperationError(
        operation="add",
        reason="Connection timeout",
        original_error=original_error,
        identifier="test-123",
    )

    assert isinstance(exc, InfrastructureError)
    assert exc.code == "DATABASE_OPERATION_ERROR"
    assert "add" in exc.message
    assert "Connection timeout" in exc.message
    assert exc.details["operation"] == "add"
    assert exc.details["reason"] == "Connection timeout"
    assert exc.details["identifier"] == "test-123"
    assert "Connection timeout" in exc.details["original_error"]


@pytest.mark.unit
=======
>>>>>>> 25e4030 (Implement test restructuring with unit, integration, and e2e tests)
def test_task_not_found_error() -> None:
    """Test TaskNotFoundError."""
    exc = TaskNotFoundError(identifier="test-uuid-123")

    assert isinstance(exc, DomainError)
    assert exc.code == "TASK_NOT_FOUND"
    assert "test-uuid-123" in exc.message
    assert exc.details["identifier"] == "test-uuid-123"
    assert "check the task ID" in exc.user_message


@pytest.mark.unit
def test_task_already_completed_error() -> None:
    """Test TaskAlreadyCompletedError."""
    exc = TaskAlreadyCompletedError(identifier="test-uuid-123")

    assert isinstance(exc, DomainError)
    assert exc.code == "TASK_ALREADY_COMPLETED"
    assert "test-uuid-123" in exc.message
    assert exc.details["identifier"] == "test-uuid-123"


@pytest.mark.unit
def test_task_already_failed_error() -> None:
    """Test TaskAlreadyFailedError."""
    exc = TaskAlreadyFailedError(identifier="test-uuid-123")

    assert isinstance(exc, DomainError)
    assert exc.code == "TASK_ALREADY_FAILED"
    assert "test-uuid-123" in exc.message


@pytest.mark.unit
def test_invalid_task_state_error() -> None:
    """Test InvalidTaskStateError."""
    exc = InvalidTaskStateError(
        identifier="test-uuid-123",
        current_state="completed",
        attempted_state="processing",
    )

    assert isinstance(exc, DomainError)
    assert exc.code == "INVALID_TASK_STATE"
    assert "completed" in exc.message
    assert "processing" in exc.message
    assert exc.details["current_state"] == "completed"
    assert exc.details["attempted_state"] == "processing"


@pytest.mark.unit
def test_invalid_audio_format_error() -> None:
    """Test InvalidAudioFormatError."""
    allowed = {".mp3", ".wav", ".m4a"}
    exc = InvalidAudioFormatError(
        filename="test.txt", extension=".txt", allowed=allowed
    )

    assert isinstance(exc, ValidationError)
    assert exc.code == "INVALID_AUDIO_FORMAT"
    assert "test.txt" in exc.message
    assert ".txt" in exc.message
    assert exc.details["filename"] == "test.txt"
    assert exc.details["extension"] == ".txt"
    assert set(exc.details["allowed_extensions"]) == allowed


@pytest.mark.unit
def test_audio_processing_error() -> None:
    """Test AudioProcessingError."""
    original = ValueError("Original error")
    exc = AudioProcessingError(reason="Failed to decode", original_error=original)

    assert isinstance(exc, DomainError)
    assert exc.code == "AUDIO_PROCESSING_ERROR"
    assert "Failed to decode" in exc.message
    assert exc.details["original_error"] == "Original error"


@pytest.mark.unit
def test_audio_too_large_error() -> None:
    """Test AudioTooLargeError."""
    exc = AudioTooLargeError(size=100_000_000, max_size=50_000_000)

    assert isinstance(exc, ValidationError)
    assert exc.code == "AUDIO_TOO_LARGE"
    assert exc.details["size"] == 100_000_000
    assert exc.details["max_size"] == 50_000_000


@pytest.mark.unit
def test_audio_too_short_error() -> None:
    """Test AudioTooShortError."""
    exc = AudioTooShortError(duration=0.5, min_duration=1.0)

    assert isinstance(exc, ValidationError)
    assert exc.code == "AUDIO_TOO_SHORT"
    assert exc.details["duration"] == pytest.approx(0.5)
    assert exc.details["min_duration"] == pytest.approx(1.0)


@pytest.mark.unit
def test_transcription_failed_error() -> None:
    """Test TranscriptionFailedError."""
    original = RuntimeError("Model failed")
    exc = TranscriptionFailedError(reason="Model error", original_error=original)

    assert isinstance(exc, DomainError)
    assert exc.code == "TRANSCRIPTION_FAILED"
    assert "Model error" in exc.message
    assert exc.details["original_error"] == "Model failed"


@pytest.mark.unit
def test_diarization_failed_error() -> None:
    """Test DiarizationFailedError."""
    exc = DiarizationFailedError(reason="No speakers found")

    assert isinstance(exc, DomainError)
    assert exc.code == "DIARIZATION_FAILED"
    assert "No speakers found" in exc.message


@pytest.mark.unit
def test_alignment_failed_error() -> None:
    """Test AlignmentFailedError."""
    exc = AlignmentFailedError(reason="Timestamp mismatch")

    assert isinstance(exc, DomainError)
    assert exc.code == "ALIGNMENT_FAILED"
    assert "Timestamp mismatch" in exc.message


@pytest.mark.unit
def test_model_load_error() -> None:
    """Test ModelLoadError."""
    original = FileNotFoundError("Model not found")
    exc = ModelLoadError(model_name="whisper-large", original_error=original)

    assert isinstance(exc, InfrastructureError)
    assert exc.code == "MODEL_LOAD_ERROR"
    assert "whisper-large" in exc.message
    assert exc.details["model_name"] == "whisper-large"
    assert "Model not found" in str(exc.details["original_error"])


@pytest.mark.unit
def test_insufficient_memory_error() -> None:
    """Test InsufficientMemoryError."""
    original = MemoryError("Out of memory")
    exc = InsufficientMemoryError(operation="transcription", original_error=original)

    assert isinstance(exc, InfrastructureError)
    assert exc.code == "INSUFFICIENT_MEMORY"
    assert "transcription" in exc.message
    assert exc.details["operation"] == "transcription"


@pytest.mark.unit
def test_file_download_error() -> None:
    """Test FileDownloadError."""
    exc = FileDownloadError(url="https://example.com/file.mp3")

    assert isinstance(exc, InfrastructureError)
    assert exc.code == "FILE_DOWNLOAD_ERROR"
    assert "https://example.com/file.mp3" in exc.message
    assert exc.details["url"] == "https://example.com/file.mp3"


@pytest.mark.unit
def test_file_validation_error() -> None:
    """Test FileValidationError."""
    exc = FileValidationError(filename="test.mp3", reason="Corrupted file")

    assert isinstance(exc, ValidationError)
    assert exc.code == "FILE_VALIDATION_ERROR"
    assert "test.mp3" in exc.message
    assert "Corrupted file" in exc.message
    assert exc.details["filename"] == "test.mp3"
    assert exc.details["reason"] == "Corrupted file"


@pytest.mark.unit
def test_unsupported_file_extension_error() -> None:
    """Test UnsupportedFileExtensionError."""
    allowed = {".mp3", ".wav"}
    exc = UnsupportedFileExtensionError(
        filename="test.txt", extension=".txt", allowed=allowed
    )

    assert isinstance(exc, ValidationError)
    assert exc.code == "UNSUPPORTED_FILE_EXTENSION"
    assert "test.txt" in exc.message
    assert ".txt" in exc.message
    assert set(exc.details["allowed_extensions"]) == allowed


@pytest.mark.unit
def test_missing_configuration_error() -> None:
    """Test MissingConfigurationError."""
    exc = MissingConfigurationError(parameter="DATABASE_URL")

    assert isinstance(exc, ConfigurationError)
    assert exc.code == "MISSING_CONFIGURATION"
    assert "DATABASE_URL" in exc.message
    assert exc.details["parameter"] == "DATABASE_URL"
