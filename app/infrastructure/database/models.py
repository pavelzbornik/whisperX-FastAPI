"""This module defines the database models for the application."""

from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class Task(Base):
    """
    Table to store tasks information.

    Attributes:
    - id: Unique identifier for each task (Primary Key).
    - uuid: Universally unique identifier for each task.
    - status: Current status of the task.
    - result: JSON data representing the result of the task.
    - file_name: Name of the file associated with the task.
    - task_type: Type/category of the task.
    - duration: Duration of the task execution.
    - error: Error message, if any, associated with the task.
    - created_at: Date and time of creation.
    - updated_at: Date and time of last update.
    """

    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique identifier for each task (Primary Key)",
    )
    uuid: Mapped[str] = mapped_column(
        String,
        default=lambda: str(uuid4()),
        comment="Universally unique identifier for each task",
    )
    status: Mapped[str] = mapped_column(String, comment="Current status of the task")
    result: Mapped[dict[str, Any]] = mapped_column(
        JSON, comment="JSON data representing the result of the task"
    )
    file_name: Mapped[str] = mapped_column(
        String, comment="Name of the file associated with the task"
    )
    url: Mapped[str] = mapped_column(
        String, comment="URL of the file associated with the task"
    )
    audio_duration: Mapped[float] = mapped_column(
        Float, comment="Duration of the audio in seconds"
    )
    language: Mapped[str] = mapped_column(
        String, comment="Language of the file associated with the task"
    )
    task_type: Mapped[str] = mapped_column(String, comment="Type/category of the task")
    task_params: Mapped[dict[str, Any]] = mapped_column(
        JSON, comment="Parameters of the task"
    )
    duration: Mapped[float] = mapped_column(
        Float, comment="Duration of the task execution"
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime, comment="Start time of the task execution"
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime, comment="End time of the task execution"
    )
    error: Mapped[str] = mapped_column(
        String, comment="Error message, if any, associated with the task"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        comment="Date and time of creation",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Date and time of last update",
    )
