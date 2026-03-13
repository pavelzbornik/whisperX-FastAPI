"""Unit of Work pattern implementation for managing transactions."""

from types import TracebackType
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.infrastructure.database.connection import AsyncSessionLocal, SyncSessionLocal
from app.infrastructure.database.repositories.sqlalchemy_task_repository import (
    AsyncSQLAlchemyTaskRepository,
    SyncSQLAlchemyTaskRepository,
)


class IUnitOfWork(Protocol):
    """
    Interface for Unit of Work pattern.

    The Unit of Work pattern maintains a list of objects affected by a business
    transaction and coordinates the writing out of changes and resolution of
    concurrency problems.
    """

    tasks: SyncSQLAlchemyTaskRepository

    def commit(self) -> None:
        """Commit the current transaction."""
        ...

    def rollback(self) -> None:
        """Rollback the current transaction."""
        ...

    def __enter__(self) -> "IUnitOfWork":
        """Enter the context manager."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager."""
        ...


class SQLAlchemyUnitOfWork:
    """
    Sync SQLAlchemy implementation of the Unit of Work pattern.

    Used exclusively by background tasks that run outside the event loop.

    Example usage:
        >>> with SQLAlchemyUnitOfWork() as uow:
        ...     task = uow.tasks.get_by_id("some-uuid")
        ...     uow.tasks.update(task.uuid, {"status": "completed"})
        ...     uow.commit()

    Attributes:
        tasks: The sync task repository instance
    """

    def __init__(self, session: Session | None = None) -> None:
        """
        Initialize the Unit of Work.

        Args:
            session: Optional database session. If not provided, a new session
                    will be created.
        """
        self._session = session
        self._should_close_session = session is None
        self._committed = False

    def __enter__(self) -> "SQLAlchemyUnitOfWork":
        """
        Enter the context manager and set up repository instances.

        Returns:
            SQLAlchemyUnitOfWork: This unit of work instance
        """
        if self._session is None:
            self._session = SyncSessionLocal()

        self.tasks = SyncSQLAlchemyTaskRepository(self._session)

        logger.debug("Unit of Work context entered")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """
        Exit the context manager and clean up resources.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        if exc_type is not None:
            logger.error(f"Exception in Unit of Work: {exc_val}")
            self.rollback()
        else:
            if not self._committed:
                logger.warning(
                    "Unit of Work exiting without explicit commit() - rolling back changes. "
                    "Did you forget to call uow.commit()?"
                )
                self.rollback()

        if self._should_close_session and self._session:
            self._session.close()
            logger.debug("Unit of Work session closed")

    def commit(self) -> None:
        """
        Commit the current transaction.

        Raises:
            Exception: If commit fails
        """
        try:
            if self._session:
                self._session.commit()
                self._committed = True
                logger.debug("Unit of Work committed successfully")
        except Exception as e:
            logger.error(f"Failed to commit Unit of Work: {str(e)}")
            self.rollback()
            raise

    def rollback(self) -> None:
        """Rollback the current transaction."""
        if self._session:
            self._session.rollback()
            logger.debug("Unit of Work rolled back")


class AsyncSQLAlchemyUnitOfWork:
    """
    Async SQLAlchemy implementation of the Unit of Work pattern.

    Used for request-scoped operations that require explicit transaction control
    spanning multiple repository calls.

    Example usage:
        >>> async with AsyncSQLAlchemyUnitOfWork() as uow:
        ...     await uow.tasks.update(task_id, {"status": "completed"})
        ...     await uow.commit()

    Attributes:
        tasks: The async task repository instance
    """

    def __init__(self, session: AsyncSession | None = None) -> None:
        """
        Initialize the async Unit of Work.

        Args:
            session: Optional async session. If not provided, a new session
                    will be created.
        """
        self._session = session
        self._should_close_session = session is None
        self._committed = False

    async def __aenter__(self) -> "AsyncSQLAlchemyUnitOfWork":
        """
        Enter the async context manager.

        Returns:
            AsyncSQLAlchemyUnitOfWork: This unit of work instance
        """
        if self._session is None:
            self._session = AsyncSessionLocal()

        self.tasks = AsyncSQLAlchemyTaskRepository(self._session)

        logger.debug("Async Unit of Work context entered")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """
        Exit the async context manager and clean up resources.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        if exc_type is not None:
            logger.error(f"Exception in Async Unit of Work: {exc_val}")
            await self.rollback()
        else:
            if not self._committed:
                logger.warning(
                    "Async Unit of Work exiting without explicit commit() - rolling back. "
                    "Did you forget to call uow.commit()?"
                )
                await self.rollback()

        if self._should_close_session and self._session:
            await self._session.close()
            logger.debug("Async Unit of Work session closed")

    async def commit(self) -> None:
        """
        Commit the current transaction.

        Raises:
            Exception: If commit fails
        """
        try:
            if self._session:
                await self._session.commit()
                self._committed = True
                logger.debug("Async Unit of Work committed successfully")
        except Exception as e:
            logger.error(f"Failed to commit Async Unit of Work: {str(e)}")
            await self.rollback()
            raise

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        if self._session:
            await self._session.rollback()
            logger.debug("Async Unit of Work rolled back")
