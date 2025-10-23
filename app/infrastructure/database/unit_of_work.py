"""Unit of Work pattern implementation for managing transactions."""

from types import TracebackType
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.repositories.sqlalchemy_task_repository import (
    SQLAlchemyTaskRepository,
)


class IUnitOfWork(Protocol):
    """
    Interface for Unit of Work pattern.

    The Unit of Work pattern maintains a list of objects affected by a business
    transaction and coordinates the writing out of changes and resolution of
    concurrency problems.
    """

    tasks: SQLAlchemyTaskRepository

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
    SQLAlchemy implementation of the Unit of Work pattern.

    This class provides a transactional context for repository operations,
    ensuring that all operations within a unit of work either succeed or fail
    together (atomicity).

    Example usage:
        >>> with SQLAlchemyUnitOfWork() as uow:
        ...     task = uow.tasks.get_by_id("some-uuid")
        ...     task.mark_as_completed(result, duration, end_time)
        ...     uow.tasks.update(task.uuid, task.to_dict())
        ...     uow.commit()  # Atomic - all or nothing

    Attributes:
        tasks: The task repository instance
    """

    def __init__(self, session: Session | None = None):
        """
        Initialize the Unit of Work.

        Args:
            session: Optional database session. If not provided, a new session
                    will be created.
        """
        self._session = session
        self._should_close_session = session is None

    def __enter__(self) -> "SQLAlchemyUnitOfWork":
        """
        Enter the context manager and set up repository instances.

        Returns:
            SQLAlchemyUnitOfWork: This unit of work instance
        """
        if self._session is None:
            self._session = SessionLocal()

        # Initialize repositories with the session
        self.tasks = SQLAlchemyTaskRepository(self._session)

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

        If an exception occurred during the context, the transaction will be
        rolled back automatically.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        if exc_type is not None:
            logger.error(f"Exception in Unit of Work: {exc_val}")
            self.rollback()

        if self._should_close_session and self._session:
            self._session.close()
            logger.debug("Unit of Work session closed")

    def commit(self) -> None:
        """
        Commit the current transaction.

        This will persist all changes made within this unit of work to the
        database.

        Raises:
            Exception: If commit fails
        """
        try:
            if self._session:
                self._session.commit()
                logger.debug("Unit of Work committed successfully")
        except Exception as e:
            logger.error(f"Failed to commit Unit of Work: {str(e)}")
            self.rollback()
            raise

    def rollback(self) -> None:
        """
        Rollback the current transaction.

        This will discard all changes made within this unit of work.
        """
        if self._session:
            self._session.rollback()
            logger.debug("Unit of Work rolled back")
