"""API DTOs (Data Transfer Objects) for task-related endpoints.

This module contains Pydantic models for API request/response validation.
These are separate from domain entities and provide API contracts.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.api.constants import AUDIO_LANGUAGE_DESCRIPTION


class CreateTaskRequest(BaseModel):
    """DTO for creating a new task via API.

    This is used for task creation requests but not directly exposed
    in the current API. Tasks are created implicitly through processing endpoints.
    """

    task_type: str = Field(..., description="Type of task to create")
    file_name: str | None = Field(None, description="Name of the file to process")
    url: str | None = Field(None, description="URL of the file to process")
    audio_duration: float | None = Field(
        None, description="Duration of the audio in seconds"
    )
    language: str | None = Field(None, description=AUDIO_LANGUAGE_DESCRIPTION)
    task_params: dict[str, Any] | None = Field(
        None, description="Additional task parameters"
    )


class TaskResponse(BaseModel):
    """DTO for returning full task details via API.

    Used for GET /task/{identifier} endpoint.
    """

    identifier: str = Field(..., description="Unique identifier for the task")
    status: str = Field(..., description="Current status of the task")
    task_type: str = Field(..., description="Type of task")
    file_name: str | None = Field(None, description="Name of the file")
    url: str | None = Field(None, description="URL of the file")
    audio_duration: float | None = Field(None, description="Duration of the audio")
    language: str | None = Field(None, description=AUDIO_LANGUAGE_DESCRIPTION)
    task_params: dict[str, Any] | None = Field(None, description="Task parameters")
    result: dict[str, Any] | None = Field(None, description="Task result data")
    error: str | None = Field(None, description="Error message if task failed")
    duration: float | None = Field(None, description="Execution duration in seconds")
    start_time: datetime | None = Field(None, description="Task start time")
    end_time: datetime | None = Field(None, description="Task end time")
    created_at: datetime = Field(..., description="Task creation time")
    updated_at: datetime = Field(..., description="Last update time")

    model_config = ConfigDict(from_attributes=True)


class TaskSummaryResponse(BaseModel):
    """DTO for returning task summary in list operations.

    Used for GET /task/all endpoint to provide a lighter response.
    """

    identifier: str = Field(..., description="Unique identifier for the task")
    status: str = Field(..., description="Current status of the task")
    task_type: str = Field(..., description="Type of task")
    file_name: str | None = Field(None, description="Name of the file")
    url: str | None = Field(None, description="URL of the file")
    audio_duration: float | None = Field(None, description="Duration of the audio")
    language: str | None = Field(None, description=AUDIO_LANGUAGE_DESCRIPTION)
    error: str | None = Field(None, description="Error message if task failed")
    duration: float | None = Field(None, description="Execution duration in seconds")
    start_time: datetime | None = Field(None, description="Task start time")
    end_time: datetime | None = Field(None, description="Task end time")

    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    """DTO for returning a list of task summaries."""

    tasks: list[TaskSummaryResponse] = Field(..., description="List of task summaries")
