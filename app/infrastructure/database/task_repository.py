"""This module contains functions to interact with the task database."""

from datetime import datetime
from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infrastructure.database.connection import (
    get_db_session,
    handle_database_errors,
)
from app.infrastructure.database.models import Task
from app.schemas import ResultTasks, TaskSimple


# Add tasks to the database
@handle_database_errors
def add_task_to_db(
    status: str,
    task_type: str,
    language: str | None = None,
    task_params: dict[str, Any] | None = None,
    file_name: str | None = None,
    url: str | None = None,
    audio_duration: float | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    session: Session = Depends(get_db_session),
) -> str:
    """
    Add a new task to the database.

    Args:
        status (str): Status of the task.
        task_type (str): Type of the task.
        language (str, optional): Language of the task. Defaults to None.
        task_params (dict, optional): Parameters of the task. Defaults to None.
        file_name (str, optional): Name of the file associated with the task. Defaults to None.
        url (str, optional): URL associated with the task. Defaults to None.
        audio_duration (float, optional): Duration of the audio file. Defaults to None.
        start_time (datetime, optional): Start time of the task. Defaults to None.
        end_time (datetime, optional): End time of the task. Defaults to None.
        session (Session, optional): Database session. Defaults to Depends(get_db_session).

    Returns:
        str: UUID of the newly created task.
    """
    task = Task(
        status=status,
        language=language,
        file_name=file_name,
        url=url,
        task_type=task_type,
        task_params=task_params,
        audio_duration=audio_duration,
        start_time=start_time,
        end_time=end_time,
    )
    session.add(task)
    session.commit()
    return str(task.uuid)


# Update task status in the database
@handle_database_errors
def update_task_status_in_db(
    identifier: str,
    update_data: dict[str, Any],
    session: Session = Depends(get_db_session),
) -> None:
    """
    Update task status and attributes in the database.

    Args:
        identifier (str): Identifier of the task to be updated.
        update_data (Dict[str, Any]): Dictionary containing the attributes to update along with their new values.
        session (Session, optional): Database session. Defaults to Depends(get_db_session).

    Returns:
        None
    """
    task = session.query(Task).filter_by(uuid=identifier).first()
    if task:
        for key, value in update_data.items():
            setattr(task, key, value)
        session.commit()


# Retrieve task status from the database
@handle_database_errors
def get_task_status_from_db(
    identifier: str, session: Session = Depends(get_db_session)
) -> dict[str, Any] | None:
    """
    Retrieve the status of a task from the database.

    Args:
        identifier (str): Identifier of the task.
        session (Session, optional): Database session. Defaults to Depends(get_db_session).

    Returns:
        dict: Dictionary containing the task status and metadata if the task exists, otherwise None.
    """
    task = session.query(Task).filter(Task.uuid == identifier).first()
    if task:
        return {
            "status": task.status,
            "result": task.result,
            "metadata": {
                "task_type": task.task_type,
                "task_params": task.task_params,
                "language": task.language,
                "file_name": task.file_name,
                "url": task.url,
                "duration": task.duration,
                "audio_duration": task.audio_duration,
                "start_time": task.start_time,
                "end_time": task.end_time,
            },
            "error": task.error,
        }
    else:
        return None


# Retrieve task status from the database
@handle_database_errors
def get_all_tasks_status_from_db(
    session: Session = Depends(get_db_session),
) -> ResultTasks:
    """
    Retrieve the status of all tasks from the database.

    Args:
        session (Session, optional): Database session. Defaults to Depends(get_db_session).

    Returns:
        ResultTasks: Object containing a list of all tasks with their status and type.
    """
    tasks = []
    # Create a query to select only the specified columns
    query = session.query(
        Task.uuid,
        Task.status,
        Task.task_type,
        Task.language,
        Task.file_name,
        Task.error,
        Task.url,
        Task.duration,
        Task.audio_duration,
        Task.start_time,
        Task.end_time,
    )
    for task in query:
        tasks.append(
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
        )
    return ResultTasks(tasks=tasks)


@handle_database_errors
def delete_task_from_db(
    identifier: str, session: Session = Depends(get_db_session)
) -> bool:
    """
    Delete a task from the database.

    Args:
        identifier (str): Identifier of the task to be deleted.
        session (Session, optional): Database session. Defaults to Depends(get_db_session).

    Returns:
        bool: True if the task was deleted, False if the task does not exist.
    """
    # Check if the identifier exists in the database
    task = session.query(Task).filter(Task.uuid == identifier).first()

    if task:
        # If the task exists, delete it from the database
        session.delete(task)
        session.commit()
        return True
    else:
        # If the task does not exist, return False
        return False
