"""Task queue interface for background task processing."""

from typing import Any, Protocol

from app.domain.entities.background_task import TaskResult


class ITaskQueue(Protocol):
    """
    Interface for background task queue implementations.

    This protocol defines the contract for task queue implementations,
    allowing different backends (FastAPI BackgroundTasks, Celery, RQ, etc.)
    to be used interchangeably without changing business logic.

    The interface follows the Repository Pattern at the service level,
    providing a clean abstraction over task queue operations.

    Example:
        >>> task_queue: ITaskQueue = FastAPITaskQueue(...)
        >>> task_id = task_queue.enqueue(
        ...     task_type="audio_processing",
        ...     parameters={"file_path": "/tmp/audio.mp3"},
        ...     max_retries=3
        ... )
        >>> result = task_queue.get_status(task_id)
        >>> if result.status == TaskStatus.FAILED:
        ...     task_queue.cancel(task_id)
    """

    def enqueue(
        self,
        task_type: str,
        parameters: dict[str, Any],
        task_id: str | None = None,
        max_retries: int = 3,
    ) -> str:
        """
        Enqueue a background task for execution.

        Args:
            task_type: Type of task (e.g., "audio_processing", "transcription")
            parameters: Serializable parameters for task execution
            task_id: Optional existing task ID (from database)
            max_retries: Maximum retry attempts on failure (default: 3)

        Returns:
            Task ID for tracking and status queries

        Raises:
            ValueError: If task_type is not registered
            InfrastructureError: If queue is unavailable
        """
        ...

    def get_status(self, task_id: str) -> TaskResult | None:
        """
        Get current status of a task.

        Args:
            task_id: Task identifier

        Returns:
            TaskResult with status and result data, or None if not found

        Example:
            >>> result = task_queue.get_status("abc-123")
            >>> if result and result.status == TaskStatus.COMPLETED:
            ...     print(result.result)
        """
        ...

    def cancel(self, task_id: str) -> bool:
        """
        Cancel a pending or running task.

        Note: Actual cancellation behavior depends on the implementation.
        FastAPI BackgroundTasks cannot truly cancel running tasks, but can
        mark them as cancelled for handlers to check. Celery and other
        distributed queues provide true cancellation.

        Args:
            task_id: Task identifier

        Returns:
            True if successfully cancelled or marked for cancellation,
            False if task not found or already completed/failed

        Example:
            >>> if task_queue.cancel("abc-123"):
            ...     print("Task cancelled")
        """
        ...
