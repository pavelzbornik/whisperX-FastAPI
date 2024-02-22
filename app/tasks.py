from uuid import uuid4
from typing import Dict, Optional, Any
from .models import TaskSimple, ResultTasks, Task
from .db import handle_database_errors, get_db_session
from sqlalchemy.orm import Session
from fastapi import Depends


# # Dictionary to store the status and results of each transcription request
# transcription_requests: Dict[str, Dict[str, Optional[str]]] = {}


# def generate_unique_identifier():
#     """Generate a unique identifier string.

#     Returns:
#        str: A unique identifier string generated from a UUID.
#     """
#     return str(uuid4())


# def get_all_requests():
#     """
#     Get all transcription requests.

#     Returns:
#        Dict: A dictionary containing all transcription requests statuses.
#     """
#     tasks = []

#     for key in transcription_requests.keys():
#         tasks.append(
#             TaskSimple(
#                 identifier=key,
#                 status=transcription_requests[key]["status"],
#                 task_type=transcription_requests[key]["metadata"]["task_type"],
#             )
#         )
#     return ResultTasks(tasks=tasks)


# def update_transcription_status(
#     identifier: str,
#     status: str,
#     result: Optional[str] = None,
#     file_name: Optional[str] = None,
#     task_type: Optional[str] = None,
#     duration: Optional[float] = None,
#     error: Optional[str] = None,
# ) -> None:
#     """
#     Update the transcription status for a request.

#     Args:
#        identifier (str): The identifier of the transcription request.
#        status (str): The new status.
#        result (Optional[str]): The transcription result (optional).
#        file_name (Optional[str]): The file name (optional).
#        task_type (Optional[str]): The task type (optional).
#        duration (Optional[float]): The duration of the transcription (optional).
#        error (Optional[str]): The error message (optional).
#     """

#     transcription_request = {
#         "status": status,
#         "result": result,
#         "metadata": {
#             "task_type": task_type,
#             "file_name": (
#                 file_name
#                 if file_name
#                 else transcription_requests.get(identifier, {})
#                 .get("metadata", {})
#                 .get("file_name")
#             ),
#             "duration": duration,
#         },
#         "error": error,
#     }

#     transcription_requests[identifier] = transcription_request


# def check_status(identifier):
#     """
#     Check the status of a transcription request.

#     Args:
#        identifier (str): The identifier of the transcription request.

#     Returns:
#        Dict: The transcription request status.
#     """
#     if identifier in transcription_requests:
#         return transcription_requests[identifier]
#     else:
#         return None


# Add tasks to the database
@handle_database_errors
def add_task_to_db(
    session,
    status,
    result=None,
    file_name=None,
    task_type=None,
    duration=None,
    error=None,
):
    task = Task(
        status=status,
        result=result,
        file_name=file_name,
        task_type=task_type,
        duration=duration,
        error=error,
    )
    session.add(task)
    session.commit()
    return task.uuid


# def update_task_status_in_db(
#     identifier,
#     status,
#     task_type,
#     result=None,
#     file_name=None,
#     duration=None,
#     error=None,
#     session: Session = Depends(get_db_session),
# ):
#     task = session.query(Task).filter_by(identifier=identifier).first()
#     if task:
#         task.status = status
#         task.result = result
#         task.file_name = file_name
#         task.task_type = task_type
#         task.duration = duration
#         task.error = error
#         session.commit()


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
    task = (
        session.query(Task)
        .filter(Task.uuid == identifier)
        .first()
    )
    if task:
        return {
            "status": task.status,
            "result": task.result,
            "metadata": {
                "task_type": task.task_type,
                "file_name": task.file_name,
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
