from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, Float, JSON, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String, default=lambda: str(uuid4()))
    status = Column(String)
    result = Column(JSON)
    file_name = Column(String)
    task_type = Column(String)
    duration = Column(Float)
    error = Column(String)
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
