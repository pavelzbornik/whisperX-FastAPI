"""SQLAlchemy implementations of the ITaskRepository interface (async and sync)."""

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseOperationError
from app.core.logging import logger
from app.domain.entities.task import Task as DomainTask
from app.infrastructure.database.mappers.task_mapper import to_domain, to_orm
from app.infrastructure.database.models import Task as ORMTask


class AsyncSQLAlchemyTaskRepository:
    """
    Async SQLAlchemy implementation of the ITaskRepository interface.

    Used for all request-scoped operations (FastAPI route handlers via DI).
    Requires an AsyncSession — never use a sync Session here.

    Attributes:
        session: The SQLAlchemy AsyncSession for executing queries
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize the repository with an async database session.

        Args:
            session: The SQLAlchemy AsyncSession
        """
        self.session = session

    async def add(self, task: DomainTask) -> str:
        """
        Add a new task to the database.

        Args:
            task: The Task entity to add

        Returns:
            str: UUID of the newly created task

        Raises:
            DatabaseOperationError: If task creation fails
        """
        try:
            if not task.uuid:
                task.uuid = str(uuid4())

            orm_task = to_orm(task)
            self.session.add(orm_task)
            await self.session.commit()
            await self.session.refresh(orm_task)

            logger.info(f"Task added successfully with UUID: {orm_task.uuid}")
            return str(orm_task.uuid)

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Failed to add task: {str(e)}")
            raise DatabaseOperationError(
                operation="add",
                reason=str(e),
                original_error=e,
                identifier=task.uuid,
            )

    async def get_by_id(self, identifier: str) -> DomainTask | None:
        """
        Get a task by its UUID.

        Args:
            identifier: The UUID of the task to retrieve

        Returns:
            DomainTask | None: The Task entity if found, None otherwise
        """
        try:
            result = await self.session.execute(
                select(ORMTask).where(ORMTask.uuid == identifier)
            )
            orm_task = result.scalars().first()

            if orm_task:
                logger.debug(f"Task found with UUID: {identifier}")
                return to_domain(orm_task)
            else:
                logger.debug(f"Task not found with UUID: {identifier}")
                return None

        except SQLAlchemyError as e:
            logger.error(f"Failed to get task by ID {identifier}: {str(e)}")
            return None

    async def get_all(self) -> list[DomainTask]:
        """
        Get all tasks from the database.

        Returns:
            list[DomainTask]: List of all Task entities
        """
        try:
            result = await self.session.execute(select(ORMTask))
            orm_tasks = result.scalars().all()
            domain_tasks = [to_domain(t) for t in orm_tasks]

            logger.debug(f"Retrieved {len(domain_tasks)} tasks from database")
            return domain_tasks

        except SQLAlchemyError as e:
            logger.error(f"Failed to get all tasks: {str(e)}")
            return []

    async def update(self, identifier: str, update_data: dict[str, Any]) -> None:
        """
        Update a task by its UUID.

        Args:
            identifier: The UUID of the task to update
            update_data: Dictionary containing the attributes to update

        Raises:
            ValueError: If the task is not found
            DatabaseOperationError: If update fails
        """
        result = await self.session.execute(
            select(ORMTask).where(ORMTask.uuid == identifier)
        )
        orm_task = result.scalars().first()

        if not orm_task:
            logger.error(f"Task not found for update with UUID: {identifier}")
            raise ValueError(f"Task not found with UUID: {identifier}")

        try:
            for key, value in update_data.items():
                if hasattr(orm_task, key):
                    setattr(orm_task, key, value)

            await self.session.commit()
            logger.info(f"Task updated successfully with UUID: {identifier}")

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Failed to update task {identifier}: {str(e)}")
            raise DatabaseOperationError(
                operation="update",
                reason=str(e),
                original_error=e,
                identifier=identifier,
            )

    async def delete(self, identifier: str) -> bool:
        """
        Delete a task by its UUID.

        Args:
            identifier: The UUID of the task to delete

        Returns:
            bool: True if the task was deleted, False if not found
        """
        try:
            result = await self.session.execute(
                select(ORMTask).where(ORMTask.uuid == identifier)
            )
            orm_task = result.scalars().first()

            if orm_task:
                await self.session.delete(orm_task)
                await self.session.commit()
                logger.info(f"Task deleted successfully with UUID: {identifier}")
                return True
            else:
                logger.debug(f"Task not found for deletion with UUID: {identifier}")
                return False

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Failed to delete task {identifier}: {str(e)}")
            return False


class SyncSQLAlchemyTaskRepository:
    """
    Sync SQLAlchemy implementation — used exclusively by background audio tasks.

    Background tasks run in a thread pool (not the event loop) and must use
    synchronous DB access. Never use this class from async FastAPI route handlers.

    Attributes:
        session: The SQLAlchemy Session for executing queries
    """

    def __init__(self, session: Session) -> None:
        """
        Initialize the repository with a sync database session.

        Args:
            session: The SQLAlchemy Session
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
            DatabaseOperationError: If task creation fails
        """
        try:
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
            raise DatabaseOperationError(
                operation="add",
                reason=str(e),
                original_error=e,
                identifier=task.uuid,
            )

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

        Raises:
            ValueError: If the task is not found
            DatabaseOperationError: If update fails
        """
        orm_task = (
            self.session.query(ORMTask).filter(ORMTask.uuid == identifier).first()
        )

        if not orm_task:
            logger.error(f"Task not found for update with UUID: {identifier}")
            raise ValueError(f"Task not found with UUID: {identifier}")

        try:
            for key, value in update_data.items():
                if hasattr(orm_task, key):
                    setattr(orm_task, key, value)

            self.session.commit()
            logger.info(f"Task updated successfully with UUID: {identifier}")

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Failed to update task {identifier}: {str(e)}")
            raise DatabaseOperationError(
                operation="update",
                reason=str(e),
                original_error=e,
                identifier=identifier,
            )

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


# Backwards-compat alias — avoid breaking external code that still imports the old name.
# Background tasks in audio_processing_service.py now import SyncSQLAlchemyTaskRepository.
SQLAlchemyTaskRepository = SyncSQLAlchemyTaskRepository
