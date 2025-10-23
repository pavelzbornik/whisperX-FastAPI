"""Repository implementations for data access."""

from app.infrastructure.database.repositories.sqlalchemy_task_repository import (
    SQLAlchemyTaskRepository,
)

__all__ = ["SQLAlchemyTaskRepository"]
