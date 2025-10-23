"""Repository interface for Task entity using Protocol for structural typing."""

from typing import Any, Protocol

from app.domain.entities.task import Task


class ITaskRepository(Protocol):
    """
    Repository interface for Task entity.

    This interface defines the contract for task data access operations.
    Implementations can use different storage backends (SQLAlchemy, NoSQL, etc.)
    without affecting the business logic that depends on this interface.

    All methods should handle their own error logging and raise appropriate
    exceptions when operations fail.
    """

    def add(self, task: Task) -> str:
        """
        Add a new task to the repository.

        Args:
            task: The Task entity to add

        Returns:
            str: UUID of the newly created task

        Raises:
            Exception: If task creation fails
        """
        ...

    def get_by_id(self, identifier: str) -> Task | None:
        """
        Get a task by its UUID.

        Args:
            identifier: The UUID of the task to retrieve

        Returns:
            Task | None: The Task entity if found, None otherwise
        """
        ...

    def get_all(self) -> list[Task]:
        """
        Get all tasks from the repository.

        Returns:
            list[Task]: List of all Task entities
        """
        ...

    def update(self, identifier: str, update_data: dict[str, Any]) -> None:
        """
        Update a task by its UUID.

        Args:
            identifier: The UUID of the task to update
            update_data: Dictionary containing the attributes to update
                        along with their new values

        Raises:
            ValueError: If the task is not found
            Exception: If update fails
        """
        ...

    def delete(self, identifier: str) -> bool:
        """
        Delete a task by its UUID.

        Args:
            identifier: The UUID of the task to delete

        Returns:
            bool: True if the task was deleted, False if not found
        """
        ...
