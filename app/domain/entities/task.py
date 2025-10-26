"""Domain entity for Task - Pure Python class representing business entity."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Task:
    """
    Domain entity representing a task in the system.

    This is a pure domain object without any database-specific concerns.
    It contains business logic and validation for task operations.

    Attributes:
        uuid: Unique identifier for the task
        status: Current status of the task (processing, completed, failed)
        task_type: Type/category of the task
        result: JSON data representing the result of the task
        file_name: Name of the file associated with the task
        url: URL of the file associated with the task
        audio_duration: Duration of the audio in seconds
        language: Language of the file associated with the task
        task_params: Parameters of the task
        duration: Duration of the task execution in seconds
        start_time: Start time of the task execution
        end_time: End time of the task execution
        error: Error message, if any, associated with the task
        retry_count: Number of retry attempts made
        max_retries: Maximum number of retry attempts allowed
        last_error: Most recent error message from retry attempts
        scheduled_at: When the task was scheduled for execution
        created_at: Date and time of creation
        updated_at: Date and time of last update
    """

    uuid: str
    status: str
    task_type: str
    result: dict[str, Any] | None = None
    file_name: str | None = None
    url: str | None = None
    audio_duration: float | None = None
    language: str | None = None
    task_params: dict[str, Any] | None = None
    duration: float | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    last_error: str | None = None
    scheduled_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def mark_as_completed(
        self, result: dict[str, Any], duration: float, end_time: datetime
    ) -> None:
        """
        Mark the task as completed with result and timing information.

        Args:
            result: The result data from task execution
            duration: Duration of task execution in seconds
            end_time: End time of task execution
        """
        self.status = "completed"
        self.result = result
        self.duration = duration
        self.end_time = end_time
        self.updated_at = datetime.utcnow()

    def mark_as_failed(self, error: str) -> None:
        """
        Mark the task as failed with error information.

        Args:
            error: Error message describing the failure
        """
        self.status = "failed"
        self.error = error
        self.end_time = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_as_processing(self, start_time: datetime) -> None:
        """
        Mark the task as processing.

        Args:
            start_time: Start time of task execution
        """
        self.status = "processing"
        self.start_time = start_time
        self.updated_at = datetime.utcnow()

    def is_processing(self) -> bool:
        """
        Check if task is currently processing.

        Returns:
            True if task status is 'processing', False otherwise
        """
        return self.status == "processing"

    def is_completed(self) -> bool:
        """
        Check if task is completed.

        Returns:
            True if task status is 'completed', False otherwise
        """
        return self.status == "completed"

    def is_failed(self) -> bool:
        """
        Check if task has failed.

        Returns:
            True if task status is 'failed', False otherwise
        """
        return self.status == "failed"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the task entity to a dictionary representation.

        Returns:
            Dictionary representation of the task
        """
        return {
            "uuid": self.uuid,
            "status": self.status,
            "task_type": self.task_type,
            "result": self.result,
            "file_name": self.file_name,
            "url": self.url,
            "audio_duration": self.audio_duration,
            "language": self.language,
            "task_params": self.task_params,
            "duration": self.duration,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "last_error": self.last_error,
            "scheduled_at": self.scheduled_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
