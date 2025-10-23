"""Mapper for converting between task API DTOs and domain entities.

This module provides functions to convert between API Data Transfer Objects (DTOs)
and domain entities. This separation ensures that changes to the API layer don't
affect the domain layer and vice versa.
"""

from uuid import uuid4

from app.api.schemas.task_schemas import (
    CreateTaskRequest,
    TaskResponse,
    TaskSummaryResponse,
)
from app.domain.entities.task import Task


class TaskMapper:
    """Mapper for converting between Task DTOs and domain entities."""

    @staticmethod
    def to_domain(dto: CreateTaskRequest, uuid: str | None = None) -> Task:
        """Convert API CreateTaskRequest DTO to domain Task entity.

        Args:
            dto: The API DTO for creating a task
            uuid: Optional UUID for the task. If not provided, a new one is generated.

        Returns:
            Task: The domain entity
        """
        task_uuid = uuid or str(uuid4())

        return Task(
            uuid=task_uuid,
            status="processing",  # New tasks start in processing state
            task_type=dto.task_type,
            file_name=dto.file_name,
            url=dto.url,
            audio_duration=dto.audio_duration,
            language=dto.language,
            task_params=dto.task_params,
        )

    @staticmethod
    def to_response(entity: Task) -> TaskResponse:
        """Convert domain Task entity to API TaskResponse DTO.

        Args:
            entity: The domain Task entity

        Returns:
            TaskResponse: The API response DTO
        """
        return TaskResponse(
            identifier=entity.uuid,
            status=entity.status,
            task_type=entity.task_type,
            file_name=entity.file_name,
            url=entity.url,
            audio_duration=entity.audio_duration,
            language=entity.language,
            task_params=entity.task_params,
            result=entity.result,
            error=entity.error,
            duration=entity.duration,
            start_time=entity.start_time,
            end_time=entity.end_time,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_summary(entity: Task) -> TaskSummaryResponse:
        """Convert domain Task entity to API TaskSummaryResponse DTO.

        This is a lighter version used for list operations.

        Args:
            entity: The domain Task entity

        Returns:
            TaskSummaryResponse: The API summary DTO
        """
        return TaskSummaryResponse(
            identifier=entity.uuid,
            status=entity.status,
            task_type=entity.task_type,
            file_name=entity.file_name,
            url=entity.url,
            audio_duration=entity.audio_duration,
            language=entity.language,
            error=entity.error,
            duration=entity.duration,
            start_time=entity.start_time,
            end_time=entity.end_time,
        )
