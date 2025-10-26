"""Custom exception hierarchy for the application.

This module defines a comprehensive exception hierarchy for domain-driven error handling,
separating business logic errors, validation errors, and infrastructure failures.
"""

import uuid
from typing import Any, Optional


class ApplicationError(Exception):
    """Base exception for all application errors.

    This is the root of our exception hierarchy. All custom exceptions should inherit
    from this class or one of its subclasses.

    Attributes:
        message: Human-readable error message for developers/logs
        code: Machine-readable error code for API responses
        correlation_id: Unique ID for request tracing across logs
        user_message: Safe message to show end users
        details: Additional error context as keyword arguments
    """

    def __init__(
        self,
        message: str,
        code: str = "APPLICATION_ERROR",
        correlation_id: Optional[str] = None,
        user_message: Optional[str] = None,
        **details: Any,
    ) -> None:
        """
        Initialize the application error.

        Args:
            message: Human-readable error message
            code: Machine-readable error code
            correlation_id: Optional unique ID for tracing (generated if not provided)
            user_message: Optional safe message for users (defaults to message)
            **details: Additional error context
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.user_message = user_message or message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dict for JSON response.

        Returns:
            Dictionary with error details suitable for API responses
        """
        return {
            "error": {
                "message": self.user_message,
                "code": self.code,
                "correlation_id": self.correlation_id,
                **self.details,
            }
        }


class DomainError(ApplicationError):
    """Business logic violation error.

    Raised when business rules are violated or domain operations cannot be completed.
    These typically map to 4xx HTTP status codes.
    """

    def __init__(self, message: str, code: str = "DOMAIN_ERROR", **kwargs: Any) -> None:
        """
        Initialize the domain error.

        Args:
            message: Human-readable error message
            code: Machine-readable error code
            **kwargs: Additional error context
        """
        super().__init__(message, code=code, **kwargs)


class ValidationError(DomainError):
    """Input validation failure error.

    Raised when user input fails validation. Maps to HTTP 422 Unprocessable Entity.
    """

    def __init__(
        self,
        message: str,
        code: str = "VALIDATION_ERROR",
        field: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the validation error.

        Args:
            message: Human-readable error message
            code: Machine-readable error code
            field: Optional field name that failed validation
            **kwargs: Additional error context
        """
        super().__init__(message, code=code, field=field, **kwargs)


class InfrastructureError(ApplicationError):
    """External system failure error.

    Raised when external dependencies (databases, APIs, file systems) fail.
    These typically map to HTTP 503 Service Unavailable.
    """

    def __init__(
        self, message: str, code: str = "INFRASTRUCTURE_ERROR", **kwargs: Any
    ) -> None:
        """
        Initialize the infrastructure error.

        Args:
            message: Human-readable error message
            code: Machine-readable error code
            **kwargs: Additional error context
        """
        super().__init__(message, code=code, **kwargs)


class ConfigurationError(ApplicationError):
    """Application configuration error.

    Raised when configuration is invalid or missing. These typically occur at startup.
    """

    def __init__(
        self, message: str, code: str = "CONFIGURATION_ERROR", **kwargs: Any
    ) -> None:
        """
        Initialize the configuration error.

        Args:
            message: Human-readable error message
            code: Machine-readable error code
            **kwargs: Additional error context
        """
        super().__init__(message, code=code, **kwargs)


# Task-related exceptions


class TaskNotFoundError(DomainError):
    """Task with given identifier not found."""

    def __init__(self, identifier: str, correlation_id: Optional[str] = None) -> None:
        """
        Initialize the task not found error.

        Args:
            identifier: The task identifier that was not found
            correlation_id: Optional correlation ID for tracing
        """
        super().__init__(
            message=f"Task with identifier '{identifier}' not found",
            code="TASK_NOT_FOUND",
            user_message="The requested task could not be found. Please check the task ID.",
            correlation_id=correlation_id,
            identifier=identifier,
        )


class TaskAlreadyCompletedError(DomainError):
    """Attempted to modify a completed task."""

    def __init__(self, identifier: str, correlation_id: Optional[str] = None) -> None:
        """
        Initialize the task already completed error.

        Args:
            identifier: The task identifier
            correlation_id: Optional correlation ID for tracing
        """
        super().__init__(
            message=f"Task '{identifier}' is already completed and cannot be modified",
            code="TASK_ALREADY_COMPLETED",
            user_message="This task has already been completed and cannot be modified.",
            correlation_id=correlation_id,
            identifier=identifier,
        )


class TaskAlreadyFailedError(DomainError):
    """Attempted to modify a failed task."""

    def __init__(self, identifier: str, correlation_id: Optional[str] = None) -> None:
        """
        Initialize the task already failed error.

        Args:
            identifier: The task identifier
            correlation_id: Optional correlation ID for tracing
        """
        super().__init__(
            message=f"Task '{identifier}' has failed and cannot be modified",
            code="TASK_ALREADY_FAILED",
            user_message="This task has failed and cannot be modified.",
            correlation_id=correlation_id,
            identifier=identifier,
        )


class InvalidTaskStateError(DomainError):
    """Invalid task state transition."""

    def __init__(
        self,
        identifier: str,
        current_state: str,
        attempted_state: str,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the invalid task state error.

        Args:
            identifier: The task identifier
            current_state: Current task state
            attempted_state: State that was attempted to transition to
            correlation_id: Optional correlation ID for tracing
        """
        super().__init__(
            message=f"Task '{identifier}' cannot transition from '{current_state}' to '{attempted_state}'",
            code="INVALID_TASK_STATE",
            user_message="Invalid task state transition.",
            correlation_id=correlation_id,
            identifier=identifier,
            current_state=current_state,
            attempted_state=attempted_state,
        )


# Audio-related exceptions


class InvalidAudioFormatError(ValidationError):
    """Audio file format not supported."""

    def __init__(self, filename: str, extension: str, allowed: set[str]) -> None:
        """
        Initialize the invalid audio format error.

        Args:
            filename: Name of the audio file
            extension: File extension that was rejected
            allowed: Set of allowed extensions
        """
        super().__init__(
            message=f"File '{filename}' has unsupported extension '{extension}'",
            code="INVALID_AUDIO_FORMAT",
            user_message=f"Audio format '{extension}' is not supported. Allowed: {', '.join(sorted(allowed))}",
            filename=filename,
            extension=extension,
            allowed_extensions=sorted(allowed),
        )


class AudioProcessingError(DomainError):
    """Audio processing failed."""

    def __init__(self, reason: str, original_error: Optional[Exception] = None) -> None:
        """
        Initialize the audio processing error.

        Args:
            reason: Reason for failure
            original_error: Optional original exception that caused this error
        """
        super().__init__(
            message=f"Audio processing failed: {reason}",
            code="AUDIO_PROCESSING_ERROR",
            user_message="Audio processing failed. Please try again or use a different audio file.",
            reason=reason,
            original_error=str(original_error) if original_error else None,
        )


class AudioTooLargeError(ValidationError):
    """Audio file size exceeded maximum."""

    def __init__(self, size: int, max_size: int) -> None:
        """
        Initialize the audio too large error.

        Args:
            size: Actual file size in bytes
            max_size: Maximum allowed size in bytes
        """
        super().__init__(
            message=f"Audio file size {size} bytes exceeds maximum {max_size} bytes",
            code="AUDIO_TOO_LARGE",
            user_message=f"Audio file is too large. Maximum size is {max_size / 1024 / 1024:.1f}MB.",
            size=size,
            max_size=max_size,
        )


class AudioTooShortError(ValidationError):
    """Audio too short to process."""

    def __init__(self, duration: float, min_duration: float) -> None:
        """
        Initialize the audio too short error.

        Args:
            duration: Actual audio duration in seconds
            min_duration: Minimum required duration in seconds
        """
        super().__init__(
            message=f"Audio duration {duration}s is less than minimum {min_duration}s",
            code="AUDIO_TOO_SHORT",
            user_message=f"Audio is too short to process. Minimum duration is {min_duration} seconds.",
            duration=duration,
            min_duration=min_duration,
        )


# ML-related exceptions


class TranscriptionFailedError(DomainError):
    """Audio transcription failed."""

    def __init__(self, reason: str, original_error: Optional[Exception] = None) -> None:
        """
        Initialize the transcription failed error.

        Args:
            reason: Reason for failure
            original_error: Optional original exception that caused this error
        """
        super().__init__(
            message=f"Transcription failed: {reason}",
            code="TRANSCRIPTION_FAILED",
            user_message="The audio transcription failed. Please try again or use a different audio file.",
            reason=reason,
            original_error=str(original_error) if original_error else None,
        )


class DiarizationFailedError(DomainError):
    """Speaker diarization failed."""

    def __init__(self, reason: str, original_error: Optional[Exception] = None) -> None:
        """
        Initialize the diarization failed error.

        Args:
            reason: Reason for failure
            original_error: Optional original exception that caused this error
        """
        super().__init__(
            message=f"Diarization failed: {reason}",
            code="DIARIZATION_FAILED",
            user_message="Speaker diarization failed. Please try again.",
            reason=reason,
            original_error=str(original_error) if original_error else None,
        )


class AlignmentFailedError(DomainError):
    """Transcript alignment failed."""

    def __init__(self, reason: str, original_error: Optional[Exception] = None) -> None:
        """
        Initialize the alignment failed error.

        Args:
            reason: Reason for failure
            original_error: Optional original exception that caused this error
        """
        super().__init__(
            message=f"Alignment failed: {reason}",
            code="ALIGNMENT_FAILED",
            user_message="Transcript alignment failed. Please try again.",
            reason=reason,
            original_error=str(original_error) if original_error else None,
        )


class ModelLoadError(InfrastructureError):
    """ML model loading failed."""

    def __init__(
        self, model_name: str, original_error: Optional[Exception] = None
    ) -> None:
        """
        Initialize the model load error.

        Args:
            model_name: Name of the model that failed to load
            original_error: Optional original exception that caused this error
        """
        super().__init__(
            message=f"Failed to load model '{model_name}'",
            code="MODEL_LOAD_ERROR",
            user_message="A system error occurred while loading the AI model. Please try again later.",
            model_name=model_name,
            original_error=str(original_error) if original_error else None,
        )


class InsufficientMemoryError(InfrastructureError):
    """Insufficient memory to complete operation."""

    def __init__(
        self, operation: str, original_error: Optional[Exception] = None
    ) -> None:
        """
        Initialize the insufficient memory error.

        Args:
            operation: Operation that failed due to memory
            original_error: Optional original exception that caused this error
        """
        super().__init__(
            message=f"Insufficient memory for operation: {operation}",
            code="INSUFFICIENT_MEMORY",
            user_message="The system ran out of memory. Please try with a smaller file or try again later.",
            operation=operation,
            original_error=str(original_error) if original_error else None,
        )


# File-related exceptions


class FileDownloadError(InfrastructureError):
    """File download from URL failed."""

    def __init__(self, url: str, original_error: Optional[Exception] = None) -> None:
        """
        Initialize the file download error.

        Args:
            url: URL that failed to download
            original_error: Optional original exception that caused this error
        """
        super().__init__(
            message=f"Failed to download file from URL: {url}",
            code="FILE_DOWNLOAD_ERROR",
            user_message="Failed to download the file from the provided URL. Please check the URL and try again.",
            url=url,
            original_error=str(original_error) if original_error else None,
        )


class FileValidationError(ValidationError):
    """File validation failed."""

    def __init__(self, filename: str, reason: str) -> None:
        """
        Initialize the file validation error.

        Args:
            filename: Name of the file that failed validation
            reason: Reason for validation failure
        """
        super().__init__(
            message=f"File validation failed for '{filename}': {reason}",
            code="FILE_VALIDATION_ERROR",
            user_message=f"File validation failed: {reason}",
            filename=filename,
            reason=reason,
        )


class UnsupportedFileExtensionError(ValidationError):
    """File extension not supported."""

    def __init__(self, filename: str, extension: str, allowed: set[str]) -> None:
        """
        Initialize the unsupported file extension error.

        Args:
            filename: Name of the file
            extension: Extension that was rejected
            allowed: Set of allowed extensions
        """
        super().__init__(
            message=f"File '{filename}' has unsupported extension '{extension}'",
            code="UNSUPPORTED_FILE_EXTENSION",
            user_message=f"File extension '{extension}' is not supported. Allowed: {', '.join(sorted(allowed))}",
            filename=filename,
            extension=extension,
            allowed_extensions=sorted(allowed),
        )


# Configuration-related exceptions


class MissingConfigurationError(ConfigurationError):
    """Required configuration parameter missing."""

    def __init__(self, parameter: str) -> None:
        """
        Initialize the missing configuration error.

        Args:
            parameter: Name of the missing configuration parameter
        """
        super().__init__(
            message=f"Required configuration parameter '{parameter}' is missing",
            code="MISSING_CONFIGURATION",
            user_message="A required configuration is missing. Please contact support.",
            parameter=parameter,
        )
