"""Dependency injection providers for FastAPI endpoints."""

from collections.abc import Generator


from app.domain.repositories.task_repository import ITaskRepository
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.repositories.sqlalchemy_task_repository import (
    SQLAlchemyTaskRepository,
)


def get_task_repository() -> Generator[ITaskRepository, None, None]:
    """
    Provide a task repository implementation for dependency injection.

    This function creates a new database session and repository instance
    for each request. The session is automatically closed when the request
    is complete.

    Yields:
        ITaskRepository: A task repository implementation

    Example:
        >>> @router.post("/tasks")
        >>> async def create_task(
        ...     repository: ITaskRepository = Depends(get_task_repository)
        ... ):
        ...     task_id = repository.add(task)
        ...     return {"id": task_id}
    """
    session = SessionLocal()
    try:
        yield SQLAlchemyTaskRepository(session)
    finally:
        session.close()


def get_task_repository_for_background() -> ITaskRepository:
    """
    Create a task repository for use in background tasks.

    This creates a new session that the caller is responsible for closing.
    Use this for background tasks that need their own session.

    Returns:
        ITaskRepository: A task repository implementation with a new session

    Example:
        >>> def background_task():
        ...     repository = get_task_repository_for_background()
        ...     try:
        ...         # Do work
        ...         pass
        ...     finally:
        ...         # Session is managed by the repository
        ...         pass
    """
    session = SessionLocal()
    return SQLAlchemyTaskRepository(session)
