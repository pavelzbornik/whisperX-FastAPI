from uuid import uuid4
from typing import Dict, Optional
from .models import Task, ResultTasks


# Dictionary to store the status and results of each transcription request
transcription_requests: Dict[str, Dict[str, Optional[str]]] = {}


def generate_unique_identifier():
    """Generate a unique identifier string.

    Returns:
       str: A unique identifier string generated from a UUID.
    """
    return str(uuid4())


def get_all_requests():
    """
    Get all transcription requests.

    Returns:
       Dict: A dictionary containing all transcription requests statuses.
    """
    tasks = []

    for key in transcription_requests.keys():
        tasks.append(
            Task(
                identifier=key,
                status=transcription_requests[key]["status"],
                task_type=transcription_requests[key]["metadata"]["task_type"],
            )
        )
    return ResultTasks(tasks=tasks)


def update_transcription_status(
    identifier: str,
    status: str,
    result: Optional[str] = None,
    file_name: Optional[str] = None,
    task_type: Optional[str] = None,
    duration: Optional[float] = None,
    error: Optional[str] = None,
) -> None:
    """
    Update the transcription status for a request.

    Args:
       identifier (str): The identifier of the transcription request.
       status (str): The new status.
       result (Optional[str]): The transcription result (optional).
       file_name (Optional[str]): The file name (optional).
       task_type (Optional[str]): The task type (optional).
       duration (Optional[float]): The duration of the transcription (optional).
       error (Optional[str]): The error message (optional).
    """

    transcription_request = {
        "status": status,
        "result": result,
        "metadata": {
            "task_type": task_type,
            "file_name": file_name
            if file_name
            else transcription_requests.get(identifier, {})
            .get("metadata", {})
            .get("file_name"),
            "duration": duration,
        },
        "error": error,
    }

    transcription_requests[identifier] = transcription_request


def check_status(identifier):
    """
    Check the status of a transcription request.

    Args:
       identifier (str): The identifier of the transcription request.

    Returns:
       Dict: The transcription request status.
    """
    if identifier in transcription_requests:
        return transcription_requests[identifier]
    else:
        return None
