"""Mapper functions for converting between domain and ORM models."""

from app.domain.entities.task import Task as DomainTask
from app.infrastructure.database.models import Task as ORMTask


def to_domain(orm_task: ORMTask) -> DomainTask:
    """
    Convert an ORM Task model to a domain Task entity.

    Args:
        orm_task: The SQLAlchemy ORM Task model

    Returns:
        DomainTask: The domain Task entity
    """
    return DomainTask(
        uuid=orm_task.uuid,
        status=orm_task.status,
        task_type=orm_task.task_type,
        result=orm_task.result,
        file_name=orm_task.file_name,
        url=orm_task.url,
        audio_duration=orm_task.audio_duration,
        language=orm_task.language,
        task_params=orm_task.task_params,
        duration=orm_task.duration,
        start_time=orm_task.start_time,
        end_time=orm_task.end_time,
        error=orm_task.error,
        created_at=orm_task.created_at,
        updated_at=orm_task.updated_at,
    )


def to_orm(domain_task: DomainTask) -> ORMTask:
    """
    Convert a domain Task entity to an ORM Task model.

    Args:
        domain_task: The domain Task entity

    Returns:
        ORMTask: The SQLAlchemy ORM Task model
    """
    orm_task = ORMTask(
        uuid=domain_task.uuid,
        status=domain_task.status,
        task_type=domain_task.task_type,
        result=domain_task.result,
        file_name=domain_task.file_name,
        url=domain_task.url,
        audio_duration=domain_task.audio_duration,
        language=domain_task.language,
        task_params=domain_task.task_params,
        duration=domain_task.duration,
        start_time=domain_task.start_time,
        end_time=domain_task.end_time,
        error=domain_task.error,
        created_at=domain_task.created_at,
        updated_at=domain_task.updated_at,
    )
    return orm_task
