"""This module contains the task management routes for the FastAPI application - API v1."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_task_management_service
from app.api.mappers.task_mapper import TaskMapper
from app.api.schemas.task_schemas import TaskListResponse
from app.core.exceptions import TaskNotFoundError
from app.core.logging import logger
from app.schemas import Metadata, Response, Result
from app.services.task_management_service import TaskManagementService

router = APIRouter(prefix="/api/v1", tags=["Tasks Management"])


@router.get("/task/all")
async def get_all_tasks_status(
    service: TaskManagementService = Depends(get_task_management_service),
) -> TaskListResponse:
    """
    Retrieve the status of all tasks.

    Args:
        service: Task management service dependency.

    Returns:
        TaskListResponse: The status of all tasks.
    """
    logger.info("Retrieving status of all tasks")
    tasks = service.get_all_tasks()

    # Convert domain tasks to API DTOs using mapper
    task_summaries = [TaskMapper.to_summary(task) for task in tasks]

    return TaskListResponse(tasks=task_summaries)


@router.get("/task/{identifier}")
async def get_transcription_status(
    identifier: str,
    service: TaskManagementService = Depends(get_task_management_service),
) -> Result:
    """
    Retrieve the status of a specific task by its identifier.

    Args:
        identifier (str): The identifier of the task.
        service: Task management service dependency.

    Returns:
        Result: The status of the task.

    Raises:
        TaskNotFoundError: If the identifier is not found.
    """
    logger.info("Retrieving status for task ID: %s", identifier)
    task = service.get_task(identifier)

    if task is None:
        logger.error("Task ID not found: %s", identifier)
        raise TaskNotFoundError(identifier)

    logger.info("Status retrieved for task ID: %s", identifier)
    return Result(
        status=task.status,
        result=task.result,
        metadata=Metadata(
            task_type=task.task_type,
            task_params=task.task_params,
            language=task.language,
            file_name=task.file_name,
            url=task.url,
            duration=task.duration,
            audio_duration=task.audio_duration,
            start_time=task.start_time,
            end_time=task.end_time,
        ),
        error=task.error,
    )


@router.delete("/task/{identifier}/delete")
async def delete_task(
    identifier: str,
    service: TaskManagementService = Depends(get_task_management_service),
) -> Response:
    """
    Delete a specific task by its identifier.

    Args:
        identifier (str): The identifier of the task.
        service: Task management service dependency.

    Returns:
        Response: Confirmation message of task deletion.

    Raises:
        TaskNotFoundError: If the task is not found.
    """
    logger.info("Deleting task ID: %s", identifier)
    if service.delete_task(identifier):
        logger.info("Task deleted: ID %s", identifier)
        return Response(identifier=identifier, message="Task deleted")
    else:
        logger.error("Task not found: ID %s", identifier)
        raise TaskNotFoundError(identifier)
