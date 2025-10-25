"""Task executor for background task execution with retry logic."""

import logging
import time
from datetime import datetime
from typing import Any

from app.domain.entities.background_task import BackgroundTask, TaskStatus
from app.domain.repositories.task_repository import ITaskRepository
from app.infrastructure.tasks.task_registry import TaskRegistry

logger = logging.getLogger(__name__)


class TaskExecutor:
    """
    Executes background tasks with retry and error handling.

    This class is responsible for executing registered task handlers,
    managing task lifecycle (status updates), implementing retry logic
    with exponential backoff, and handling errors gracefully.

    The executor follows the Command Pattern, where tasks are executed
    based on their type and parameters without knowing the implementation
    details of each handler.

    Architecture:
        - Loads task definition from database
        - Retrieves handler from registry
        - Executes handler with parameters
        - Updates task status throughout lifecycle
        - Implements retry logic on failure
        - Stores results in database

    Example:
        >>> executor = TaskExecutor(registry, repository)
        >>> task = BackgroundTask(
        ...     task_id="123",
        ...     task_type="audio_processing",
        ...     parameters={"file_path": "/tmp/audio.mp3"}
        ... )
        >>> executor.execute(task)
    """

    def __init__(
        self, task_registry: TaskRegistry, task_repository: ITaskRepository
    ) -> None:
        """
        Initialize with task registry and repository.

        Args:
            task_registry: Registry containing task handlers
            task_repository: Repository for task persistence
        """
        self.registry = task_registry
        self.repository = task_repository
        logger.info("TaskExecutor initialized")

    def execute(self, task: BackgroundTask) -> Any:
        """
        Execute a background task with retry logic.

        This method orchestrates the complete task execution lifecycle:
        1. Mark task as processing
        2. Check for cancellation
        3. Retrieve and execute handler
        4. Handle success or failure
        5. Implement retry logic if needed
        6. Update task status in database

        Args:
            task: Background task to execute

        Returns:
            Result from successful task execution

        Raises:
            ValueError: If task type not registered
            Exception: Re-raises handler exceptions after retry attempts

        Example:
            >>> task = BackgroundTask(
            ...     task_id="123",
            ...     task_type="audio_processing",
            ...     parameters={"file_path": "/tmp/audio.mp3"}
            ... )
            >>> result = executor.execute(task)
        """
        logger.info(
            f"Starting execution of task {task.task_id} (type: {task.task_type})"
        )

        # Update status to processing
        task.status = TaskStatus.PROCESSING
        task.started_at = datetime.utcnow()
        self._update_task_db(task)

        # Check if cancelled
        if self._is_cancelled(task.task_id):
            logger.info(f"Task {task.task_id} was cancelled")
            return None

        try:
            # Get handler from registry
            handler = self.registry.get_handler(task.task_type)
            if not handler:
                raise ValueError(
                    f"No handler registered for task type: {task.task_type}"
                )

            # Execute handler
            start_time = time.time()
            result = handler(**task.parameters)
            duration = time.time() - start_time

            # Update as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            self._update_task_result(task.task_id, result, duration)

            logger.info(
                f"Task {task.task_id} completed successfully in {duration:.2f}s"
            )
            return result

        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {str(e)}", exc_info=True)

            # Handle retry
            if task.retry_count < task.max_retries:
                self._schedule_retry(task, str(e))
            else:
                self._mark_failed(task, str(e))

            raise

    def _is_cancelled(self, task_id: str) -> bool:
        """
        Check if task was cancelled.

        Args:
            task_id: Task identifier

        Returns:
            True if task status is CANCELLED, False otherwise
        """
        task = self.repository.get_by_id(task_id)
        return task is not None and task.status == TaskStatus.CANCELLED.value

    def _schedule_retry(self, task: BackgroundTask, error: str) -> None:
        """
        Schedule task retry with exponential backoff.

        Implements exponential backoff strategy:
        - Retry 1: 2 seconds
        - Retry 2: 4 seconds
        - Retry 3: 8 seconds

        Args:
            task: Background task to retry
            error: Error message from failed attempt

        Note:
            FastAPI BackgroundTasks doesn't support delayed execution.
            For Celery migration, use: self.execute.apply_async((task,), countdown=backoff)
        """
        task.retry_count += 1
        task.error_message = error
        task.status = TaskStatus.QUEUED

        # Calculate backoff delay
        backoff_seconds = 2**task.retry_count  # 2, 4, 8 seconds

        logger.info(
            f"Scheduling retry {task.retry_count}/{task.max_retries} "
            f"for task {task.task_id} in {backoff_seconds}s"
        )

        self._update_task_db(task)

        # Note: In FastAPI, we can't actually delay execution
        # For Celery migration: self.execute.apply_async((task,), countdown=backoff_seconds)

    def _mark_failed(self, task: BackgroundTask, error: str) -> None:
        """
        Mark task as permanently failed.

        Args:
            task: Background task that failed
            error: Error message from final failed attempt
        """
        task.status = TaskStatus.FAILED
        task.error_message = error
        task.completed_at = datetime.utcnow()
        self._update_task_db(task)

        logger.error(
            f"Task {task.task_id} permanently failed after "
            f"{task.retry_count} retries: {error}"
        )

    def _update_task_db(self, task: BackgroundTask) -> None:
        """
        Update task in database.

        Args:
            task: Background task with updated data
        """
        self.repository.update(
            identifier=task.task_id,
            update_data={
                "status": task.status.value,
                "retry_count": task.retry_count,
                "last_error": task.error_message,
                "start_time": task.started_at,
                "end_time": task.completed_at,
            },
        )

    def _update_task_result(self, task_id: str, result: Any, duration: float) -> None:
        """
        Update task with result.

        Args:
            task_id: Task identifier
            result: Task execution result
            duration: Execution duration in seconds
        """
        self.repository.update(
            identifier=task_id,
            update_data={
                "status": TaskStatus.COMPLETED.value,
                "result": result,
                "duration": duration,
                "end_time": datetime.utcnow(),
            },
        )
