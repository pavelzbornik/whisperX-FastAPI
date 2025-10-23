"""This module contains the task management routes for the FastAPI application."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_task_repository
from app.core.logging import logger
from app.domain.repositories.task_repository import ITaskRepository
from app.schemas import Response, Result, ResultTasks, TaskSimple, Metadata

task_router = APIRouter()


@task_router.get("/task/all", tags=["Tasks Management"])
async def get_all_tasks_status(
    repository: ITaskRepository = Depends(get_task_repository),
) -> ResultTasks:
    """
    Retrieve the status of all tasks.

    Args:
        repository (ITaskRepository): Task repository dependency.

    Returns:
        ResultTasks: The status of all tasks.
    """
    logger.info("Retrieving status of all tasks")
    tasks = repository.get_all()

    # Convert domain tasks to TaskSimple schema
    task_simples = [
        TaskSimple(
            identifier=task.uuid,
            status=task.status,
            task_type=task.task_type,
            language=task.language,
            file_name=task.file_name,
            error=task.error,
            url=task.url,
            duration=task.duration,
            audio_duration=task.audio_duration,
            start_time=task.start_time,
            end_time=task.end_time,
        )
        for task in tasks
    ]

    return ResultTasks(tasks=task_simples)


@task_router.get("/task/{identifier}", tags=["Tasks Management"])
async def get_transcription_status(
    identifier: str,
    repository: ITaskRepository = Depends(get_task_repository),
) -> Result:
    """
    Retrieve the status of a specific task by its identifier.

    Args:
        identifier (str): The identifier of the task.
        repository (ITaskRepository): Task repository dependency.

    Returns:
        Result: The status of the task.

    Raises:
        HTTPException: If the identifier is not found.
    """
    logger.info("Retrieving status for task ID: %s", identifier)
    task = repository.get_by_id(identifier)

    if task is not None:
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
    else:
        logger.error("Task ID not found: %s", identifier)
        raise HTTPException(status_code=404, detail="Identifier not found")


@task_router.delete("/task/{identifier}/delete", tags=["Tasks Management"])
async def delete_task(
    identifier: str,
    repository: ITaskRepository = Depends(get_task_repository),
) -> Response:
    """
    Delete a specific task by its identifier.

    Args:
        identifier (str): The identifier of the task.
        repository (ITaskRepository): Task repository dependency.

    Returns:
        Response: Confirmation message of task deletion.

    Raises:
        HTTPException: If the task is not found.
    """
    logger.info("Deleting task ID: %s", identifier)
    if repository.delete(identifier):
        logger.info("Task deleted: ID %s", identifier)
        return Response(identifier=identifier, message="Task deleted")
    else:
        logger.error("Task not found: ID %s", identifier)
        raise HTTPException(status_code=404, detail="Task not found")
