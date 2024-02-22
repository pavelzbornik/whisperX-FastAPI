from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, Float, JSON, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

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
    result = Column(
        JSON, comment="JSON data representing the result of the task"
    )
    file_name = Column(
        String, comment="Name of the file associated with the task"
    )
    task_type = Column(String, comment="Type/category of the task")
    duration = Column(Float, comment="Duration of the task execution")
    error = Column(
        String, comment="Error message, if any, associated with the task"
    )
    created_at = Column(
        DateTime, default=datetime.utcnow, comment="Date and time of creation"
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Date and time of last update",
    )


class Response(BaseModel):
    identifier: str
    message: str


class Metadata(BaseModel):
    task_type: str
    file_name: Optional[str]
    duration: Optional[float]


class TaskSimple(BaseModel):
    identifier: str
    status: str
    task_type: str


class ResultTasks(BaseModel):
    tasks: List[TaskSimple]


class TranscriptionSegment(BaseModel):
    start: float
    end: float
    text: str


class Segment(BaseModel):
    start: float
    end: float
    text: Optional[str]
    speaker: Optional[str]


class Word(BaseModel):
    word: str
    start: float
    end: float
    score: float


class AlingmentSegment(BaseModel):
    start: float
    end: float
    text: str
    words: List[Word]


class AlignedTranscription(BaseModel):
    segments: List[AlingmentSegment]
    word_segments: List[Word]


class DiarizationSegment(BaseModel):
    label: str
    speaker: str
    start: float
    end: float


class DiaredTrancript(BaseModel):
    segments: List[Segment]


class Transcript(BaseModel):
    segments: List[TranscriptionSegment]
    language: Optional[str]


class TranscriptInput(BaseModel):
    transcript: Transcript


class Result(BaseModel):
    status: str
    result: Any
    metadata: Metadata
    error: Optional[str]
