"""FastAPI BackgroundTasks implementation of task queue interface."""

import logging
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks

from app.domain.entities.background_task import BackgroundTask, TaskResult, TaskStatus
from app.domain.repositories.task_repository import ITaskRepository
from app.infrastructure.tasks.task_executor import TaskExecutor

logger = logging.getLogger(__name__)


class FastAPITaskQueue:
    """
    FastAPI BackgroundTasks implementation of ITaskQueue.

    This class wraps FastAPI's BackgroundTasks to provide a consistent
    interface for task queuing, enabling future migration to distributed
    task queues (Celery, RQ) without changing business logic.

    Architecture:
        - Implements ITaskQueue protocol
        - Wraps FastAPI BackgroundTasks for task execution
        - Persists tasks to database immediately
        - Updates task status throughout lifecycle
        - Supports task cancellation (marking only)

    Limitations:
        - No true distributed processing (single process)
        - Limited retry capabilities (no delayed retry)
        - Cannot cancel already-running tasks
        - Tasks lost if application crashes

    Migration Path:
        Replace with CeleryTaskQueue or RQTaskQueue for production
        scale. Business logic remains unchanged.

    Example:
        >>> task_queue = FastAPITaskQueue(background_tasks, executor, repository)
        >>> task_id = task_queue.enqueue(
        ...     task_type="audio_processing",
        ...     parameters={"file_path": "/tmp/audio.mp3"},
        ...     max_retries=3
        ... )
        >>> result = task_queue.get_status(task_id)
    """

    def __init__(
        self,
        background_tasks: BackgroundTasks,
        task_executor: TaskExecutor,
        task_repository: ITaskRepository,
    ) -> None:
        """
        Initialize with FastAPI BackgroundTasks and dependencies.

        Args:
            background_tasks: FastAPI BackgroundTasks instance
            task_executor: Task executor for running tasks
            task_repository: Repository for task persistence
        """
        self.background_tasks = background_tasks
        self.task_executor = task_executor
        self.task_repository = task_repository
        logger.info("FastAPITaskQueue initialized")

    def enqueue(
        self,
        task_type: str,
        parameters: dict[str, Any],
        task_id: str | None = None,
        max_retries: int = 3,
    ) -> str:
        """
        Enqueue task using FastAPI BackgroundTasks.

        This method creates a background task entity, persists it to the
        database, and schedules it with FastAPI's background execution.

        Args:
            task_type: Type of task (e.g., "audio_processing")
            parameters: Serializable parameters for task execution
            task_id: Optional existing task ID (from database)
            max_retries: Maximum retry attempts on failure (default: 3)

        Returns:
            Task ID for tracking and status queries

        Example:
            >>> task_id = task_queue.enqueue(
            ...     task_type="audio_processing",
            ...     parameters={"file_path": "/tmp/audio.mp3"},
            ...     max_retries=3
            ... )
        """
        # Create background task entity
        bg_task = BackgroundTask(
            task_id=task_id or self._generate_task_id(),
            task_type=task_type,
            parameters=parameters,
            max_retries=max_retries,
        )

        # Persist to database with initial status
        self.task_repository.update(
            identifier=bg_task.task_id,
            update_data={
                "status": bg_task.status.value,
                "retry_count": bg_task.retry_count,
                "max_retries": bg_task.max_retries,
                "scheduled_at": bg_task.created_at,
            },
        )

        # Schedule with FastAPI
        self.background_tasks.add_task(self.task_executor.execute, bg_task)

        logger.info(f"Enqueued task {bg_task.task_id} of type {task_type}")

        return bg_task.task_id

    def get_status(self, task_id: str) -> TaskResult | None:
        """
        Get task status from database.

        Args:
            task_id: Task identifier

        Returns:
            TaskResult with status and result data, or None if not found

        Example:
            >>> result = task_queue.get_status("abc-123")
            >>> if result and result.status == TaskStatus.COMPLETED:
            ...     print(result.result)
        """
        task = self.task_repository.get_by_id(task_id)
        if not task:
            return None

        return TaskResult(
            task_id=task.uuid,
            status=TaskStatus(task.status),
            result=task.result,
            error=task.last_error or task.error,
            retry_count=task.retry_count,
            duration_seconds=task.duration,
        )

    def cancel(self, task_id: str) -> bool:
        """
        Cancel task (mark as cancelled in database).

        Note: FastAPI BackgroundTasks doesn't support actual cancellation
        of running tasks. This method marks the task as cancelled so the
        handler can check status and abort execution.

        For true cancellation, migrate to Celery or RQ which support
        revoking tasks.

        Args:
            task_id: Task identifier

        Returns:
            True if successfully marked as cancelled, False if task not
            found or already completed/failed

        Example:
            >>> if task_queue.cancel("abc-123"):
            ...     print("Task marked for cancellation")
        """
        task = self.task_repository.get_by_id(task_id)
        if not task or task.status not in [
            TaskStatus.PENDING.value,
            TaskStatus.QUEUED.value,
        ]:
            logger.warning(
                f"Cannot cancel task {task_id}: not found or not in cancellable state"
            )
            return False

        self.task_repository.update(
            identifier=task_id,
            update_data={"status": TaskStatus.CANCELLED.value},
        )
        logger.info(f"Task {task_id} marked as cancelled")
        return True

    def _generate_task_id(self) -> str:
        """
        Generate unique task ID.

        Returns:
            UUID string for task identification
        """
        return str(uuid4())
