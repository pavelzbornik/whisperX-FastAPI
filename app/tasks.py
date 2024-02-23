from typing import Dict, Any
from .models import Task
from .schemas import TaskSimple, ResultTasks
from .db import handle_database_errors, get_db_session
from sqlalchemy.orm import Session
from fastapi import Depends


# Add tasks to the database
@handle_database_errors
def add_task_to_db(
    session,
    status,
    task_type,
    language=None,
    task_params=None,
    file_name=None,
    url=None,
):
    task = Task(
        status=status,
        language=language,
        file_name=file_name,
        url=url,
        task_type=task_type,
        task_params=task_params,
    )
    session.add(task)
    session.commit()
    return task.uuid


# Update task status in the database
@handle_database_errors
def update_task_status_in_db(
    identifier: str,
    update_data: Dict[str, Any],
    session: Session = Depends(get_db_session),
):
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
    identifier, session: Session = Depends(get_db_session)
):
    # task = session.query(Task).filter_by(id=identifier).first()
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
            },
            "error": task.error,
        }
    else:
        return None


# Retrieve task status from the database
@handle_database_errors
def get_all_tasks_status_from_db(session: Session = Depends(get_db_session)):
    tasks = []
    # Define the columns you want to select
    columns = [Task.uuid, Task.status, Task.task_type]

    # Create a query to select only the specified columns
    query = session.query(*columns)
    for task in query:
        tasks.append(
            TaskSimple(
                identifier=task.uuid,
                status=task.status,
                task_type=task.task_type,
            )
        )
    return ResultTasks(tasks=tasks)


@handle_database_errors
def delete_task_from_db(identifier: str, session: Session):
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
