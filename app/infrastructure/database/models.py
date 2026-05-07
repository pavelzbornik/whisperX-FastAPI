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
    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="JSON data representing the result of the task"
    )
    file_name: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Name of the file associated with the task"
    )
    url: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="URL of the file associated with the task"
    )
    callback_url: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Callback URL to POST results to"
    )
    audio_duration: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Duration of the audio in seconds"
    )
    language: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Language of the file associated with the task"
    )
    task_type: Mapped[str] = mapped_column(String, comment="Type/category of the task")
    task_params: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="Parameters of the task"
    )
    duration: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Duration of the task execution"
    )
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Start time of the task execution",
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="End time of the task execution"
    )
    error: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Error message, if any, associated with the task"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        comment="Date and time of creation",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Date and time of last update",
    )


class SpeakerEmbedding(Base):
    """
    Table to store speaker embeddings for identification.

    Attributes:
    - id: Unique identifier (Primary Key).
    - uuid: Universally unique identifier for each speaker embedding.
    - task_uuid: Optional link to the originating diarization task.
    - speaker_label: User-facing name for the speaker.
    - description: Optional free-text description of the speaker.
    - embedding: Speaker embedding vector stored as JSON array.
    - created_at: Date and time of creation.
    """

    __tablename__ = "speaker_embeddings"
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique identifier (Primary Key)",
    )
    uuid: Mapped[str] = mapped_column(
        String,
        unique=True,
        default=lambda: str(uuid4()),
        comment="Universally unique identifier for each speaker embedding",
    )
    task_uuid: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
        comment="Optional link to the originating diarization task",
    )
    speaker_label: Mapped[str] = mapped_column(
        String, comment="User-facing name for the speaker"
    )
    description: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Free-text description of the speaker"
    )
    embedding: Mapped[list[float]] = mapped_column(
        JSON, comment="Speaker embedding vector"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        comment="Date and time of creation",
    )
