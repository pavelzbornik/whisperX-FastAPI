"""Service for task management operations."""

from typing import Any

from app.core.logging import logger
from app.core.logging.audit_logger import AuditLogger
from app.domain.entities.task import Task
from app.domain.repositories.task_repository import ITaskRepository


class TaskManagementService:
    """Service for managing task operations.

    This service handles all business logic for task management including
    creating, retrieving, updating, and deleting tasks. All operations
    are audited for security and compliance.
    """

    def __init__(self, repository: ITaskRepository) -> None:
        """Initialize the task management service.

        Args:
            repository: Task repository for data persistence
        """
        self.repository = repository

    async def create_task(self, task: Task) -> str:
        """Create a new task in the repository.

        Args:
            task: The domain task entity to create

        Returns:
            The UUID of the created task
        """
        logger.debug("Creating new task: %s", task.uuid)
        identifier = await self.repository.add(task)
        logger.info("Task created with UUID: %s", identifier)

        AuditLogger.log_task_created(
            task_id=identifier,
            task_type=task.task_type or "unknown",
        )

        return identifier

    async def get_task(self, identifier: str) -> Task | None:
        """Retrieve a task by its identifier.

        Args:
            identifier: The UUID of the task to retrieve

        Returns:
            The task domain entity if found, None otherwise
        """
        logger.debug("Retrieving task with identifier: %s", identifier)
        task = await self.repository.get_by_id(identifier)

        if task:
            logger.debug("Task found: %s", identifier)
        else:
            logger.debug("Task not found: %s", identifier)

        return task

    async def get_all_tasks(self) -> list[Task]:
        """Retrieve all tasks from the repository.

        Returns:
            List of all task domain entities
        """
        logger.debug("Retrieving all tasks")
        tasks = await self.repository.get_all()
        logger.info("Retrieved %d tasks", len(tasks))
        return tasks

    async def delete_task(
        self,
        identifier: str,
        reason: str | None = None,
    ) -> bool:
        """Delete a task by its identifier.

        Args:
            identifier: The UUID of the task to delete
            reason: Deletion reason (optional)

        Returns:
            True if the task was deleted, False if not found
        """
        logger.debug("Deleting task with identifier: %s", identifier)
        result = await self.repository.delete(identifier)

        if result:
            logger.info("Task deleted successfully: %s", identifier)
            AuditLogger.log_task_deleted(
                task_id=identifier,
                reason=reason,
            )
        else:
            logger.warning("Task not found for deletion: %s", identifier)

        return result

    async def update_task_status(
        self,
        identifier: str,
        update_data: dict[str, Any],
    ) -> None:
        """Update task status and related information.

        Args:
            identifier: The UUID of the task to update
            update_data: Dictionary of fields to update
        """
        logger.debug("Updating task %s with data: %s", identifier, update_data.keys())
        await self.repository.update(identifier, update_data)
        logger.info("Task updated successfully: %s", identifier)

        # If task is being marked as completed, audit log it
        if update_data.get("status") == "completed":
            duration = update_data.get("duration", 0.0)
            AuditLogger.log_task_completed(
                task_id=identifier,
                duration=duration,
            )
