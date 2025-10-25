"""Background task entity for queue processing."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    """
    Background task definition for queue processing.

    This entity represents a task that will be executed asynchronously
    in the background. It contains all necessary information for task
    execution, retry logic, and status tracking.

    Attributes:
        task_id: Unique identifier for the task
        task_type: Type/category of the task (e.g., "audio_processing")
        parameters: Serializable parameters for task execution
        status: Current status of the task
        retry_count: Number of retry attempts made
        max_retries: Maximum number of retry attempts allowed
        error_message: Error message from last failed attempt
        created_at: Timestamp when task was created
        started_at: Timestamp when task execution started
        completed_at: Timestamp when task completed or failed
    """

    task_id: str
    task_type: str
    parameters: dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    error_message: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Initialize timestamps."""
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def serialize(self) -> str:
        """
        Serialize to JSON string for storage.

        Returns:
            JSON string representation of the task
        """
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat() if self.created_at else None
        data["started_at"] = self.started_at.isoformat() if self.started_at else None
        data["completed_at"] = (
            self.completed_at.isoformat() if self.completed_at else None
        )
        data["status"] = self.status.value
        return json.dumps(data)

    @classmethod
    def deserialize(cls, json_str: str) -> "BackgroundTask":
        """
        Deserialize from JSON string.

        Args:
            json_str: JSON string representation

        Returns:
            BackgroundTask instance
        """
        data = json.loads(json_str)
        data["status"] = TaskStatus(data["status"])
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])
        return cls(**data)


@dataclass
class TaskResult:
    """
    Task execution result.

    This dataclass encapsulates the result of a task execution,
    including status, result data, errors, and performance metrics.

    Attributes:
        task_id: Task identifier
        status: Final status of the task
        result: Result data from successful execution
        error: Error message from failed execution
        retry_count: Number of retry attempts made
        duration_seconds: Total execution time in seconds
    """

    task_id: str
    status: TaskStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    retry_count: int = 0
    duration_seconds: float | None = None
