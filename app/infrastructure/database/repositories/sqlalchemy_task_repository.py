"""SQLAlchemy implementation of the ITaskRepository interface."""

from typing import Any
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.domain.entities.task import Task as DomainTask
from app.infrastructure.database.mappers.task_mapper import to_domain, to_orm
from app.infrastructure.database.models import Task as ORMTask


class SQLAlchemyTaskRepository:
    """
    SQLAlchemy implementation of the ITaskRepository interface.

    This class provides concrete implementations of all task repository
    operations using SQLAlchemy for database access.

    Attributes:
        session: The SQLAlchemy database session for executing queries
    """

    def __init__(self, session: Session):
        """
        Initialize the repository with a database session.

        Args:
            session: The SQLAlchemy database session
        """
        self.session = session

    def add(self, task: DomainTask) -> str:
        """
        Add a new task to the database.

        Args:
            task: The Task entity to add

        Returns:
            str: UUID of the newly created task

        Raises:
            Exception: If task creation fails
        """
        try:
            # If task doesn't have a UUID yet, generate one
            if not task.uuid:
                task.uuid = str(uuid4())

            orm_task = to_orm(task)
            self.session.add(orm_task)
            self.session.commit()
            self.session.refresh(orm_task)

            logger.info(f"Task added successfully with UUID: {orm_task.uuid}")
            return str(orm_task.uuid)

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Failed to add task: {str(e)}")
            raise Exception(f"Failed to add task: {str(e)}")

    def get_by_id(self, identifier: str) -> DomainTask | None:
        """
        Get a task by its UUID.

        Args:
            identifier: The UUID of the task to retrieve

        Returns:
            DomainTask | None: The Task entity if found, None otherwise
        """
        try:
            orm_task = (
                self.session.query(ORMTask).filter(ORMTask.uuid == identifier).first()
            )

            if orm_task:
                logger.debug(f"Task found with UUID: {identifier}")
                return to_domain(orm_task)
            else:
                logger.debug(f"Task not found with UUID: {identifier}")
                return None

        except SQLAlchemyError as e:
            logger.error(f"Failed to get task by ID {identifier}: {str(e)}")
            return None

    def get_all(self) -> list[DomainTask]:
        """
        Get all tasks from the database.

        Returns:
            list[DomainTask]: List of all Task entities
        """
        try:
            orm_tasks = self.session.query(ORMTask).all()
            domain_tasks = [to_domain(orm_task) for orm_task in orm_tasks]

            logger.debug(f"Retrieved {len(domain_tasks)} tasks from database")
            return domain_tasks

        except SQLAlchemyError as e:
            logger.error(f"Failed to get all tasks: {str(e)}")
            return []

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
        try:
            orm_task = (
                self.session.query(ORMTask).filter(ORMTask.uuid == identifier).first()
            )

            if not orm_task:
                logger.error(f"Task not found for update with UUID: {identifier}")
                raise ValueError(f"Task not found with UUID: {identifier}")

            # Update attributes
            for key, value in update_data.items():
                if hasattr(orm_task, key):
                    setattr(orm_task, key, value)

            self.session.commit()
            logger.info(f"Task updated successfully with UUID: {identifier}")

        except ValueError:
            # Re-raise ValueError as is
            raise
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Failed to update task {identifier}: {str(e)}")
            raise Exception(f"Failed to update task: {str(e)}")

    def delete(self, identifier: str) -> bool:
        """
        Delete a task by its UUID.

        Args:
            identifier: The UUID of the task to delete

        Returns:
            bool: True if the task was deleted, False if not found
        """
        try:
            orm_task = (
                self.session.query(ORMTask).filter(ORMTask.uuid == identifier).first()
            )

            if orm_task:
                self.session.delete(orm_task)
                self.session.commit()
                logger.info(f"Task deleted successfully with UUID: {identifier}")
                return True
            else:
                logger.debug(f"Task not found for deletion with UUID: {identifier}")
                return False

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Failed to delete task {identifier}: {str(e)}")
            return False
