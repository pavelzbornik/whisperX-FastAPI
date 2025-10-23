"""Dependency injection providers for FastAPI endpoints."""

from collections.abc import Generator

from fastapi import Depends

from app.domain.repositories.task_repository import ITaskRepository
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.repositories.sqlalchemy_task_repository import (
    SQLAlchemyTaskRepository,
)
from app.services.file_service import FileService
from app.services.task_management_service import TaskManagementService


def get_task_repository() -> Generator[ITaskRepository, None, None]:
    """
    Provide a task repository implementation for dependency injection.

    This function creates a new database session and repository instance
    for each request. The session is automatically closed when the request
    is complete.

    Background tasks create their own sessions directly using SessionLocal()
    and SQLAlchemyTaskRepository() rather than using dependency injection.

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


def get_file_service() -> FileService:
    """
    Provide a FileService instance for dependency injection.

    FileService is stateless, so we return a new instance for each request.

    Returns:
        FileService: A file service instance
    """
    return FileService()


def get_task_management_service(
    repository: ITaskRepository = Depends(get_task_repository),
) -> Generator[TaskManagementService, None, None]:
    """
    Provide a TaskManagementService instance for dependency injection.

    The service is initialized with a task repository.

    Args:
        repository: Task repository from get_task_repository

    Yields:
        TaskManagementService: A task management service instance
    """
    yield TaskManagementService(repository)
