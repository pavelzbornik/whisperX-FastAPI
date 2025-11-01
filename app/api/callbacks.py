"""Callback router for task notifications."""

from fastapi import APIRouter

from ..schemas import Result, TaskEventReceived


task_callback_router = APIRouter()


@task_callback_router.post(
    "{$callback_url}",
    response_model=TaskEventReceived,
    summary="Task completion callback",
    description="Webhook endpoint that receives task completion notifications",
    tags=["Callbacks"],
    operation_id="task_completion_callback",
)
def task_notification(body: Result) -> TaskEventReceived:
    """
    Receive task completion notifications.

    This endpoint is called automatically when a task completes or fails if a valid callback url was provided.

    Args:
        body (Result): The task result containing status, result data, metadata, and optional error

    Returns:
        TaskEventReceived: Confirmation that the callback was received
    """
    return TaskEventReceived(ok=True)
