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
