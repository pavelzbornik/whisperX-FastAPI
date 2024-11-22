"""This module defines the database models for the application."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


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
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique identifier for each task (Primary Key)",
    )
    uuid = Column(
        String,
        default=lambda: str(uuid4()),
        comment="Universally unique identifier for each task",
    )
    status = Column(String, comment="Current status of the task")
    result = Column(JSON, comment="JSON data representing the result of the task")
    file_name = Column(String, comment="Name of the file associated with the task")
    url = Column(String, comment="URL of the file associated with the task")
    audio_duration = Column(Float, comment="Duration of the audio in seconds")
    language = Column(String, comment="Language of the file associated with the task")
    task_type = Column(String, comment="Type/category of the task")
    task_params = Column(JSON, comment="Parameters of the task")
    duration = Column(Float, comment="Duration of the task execution")
    start_time = Column(DateTime, comment="Start time of the task execution")
    end_time = Column(DateTime, comment="End time of the task execution")
    error = Column(String, comment="Error message, if any, associated with the task")
    created_at = Column(
        DateTime, default=datetime.utcnow, comment="Date and time of creation"
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Date and time of last update",
    )
