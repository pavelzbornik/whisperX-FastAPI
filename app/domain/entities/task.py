"""Domain entity for Task - Pure Python class representing business entity."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

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
        self.updated_at = datetime.now(timezone.utc)

    def mark_as_failed(self, error: str) -> None:
        """
        Mark the task as failed with error information.

        Args:
            error: Error message describing the failure
        """
        self.status = "failed"
        self.error = error
        self.end_time = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def mark_as_processing(self, start_time: datetime) -> None:
        """
        Mark the task as processing.

        Args:
            start_time: Start time of task execution
        """
        self.status = "processing"
        self.start_time = start_time
        self.updated_at = datetime.now(timezone.utc)

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
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
