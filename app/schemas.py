from pydantic import BaseModel
from typing import Optional, List, Any
from enum import Enum
from whisperx import utils

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


class ComputeType(str, Enum):
    float16 = "float16"
    float32 = "float32"
    int8 = "int8"


class WhisperModel(str, Enum):
    tiny = "tiny"
    tiny_en = "tiny.en"
    base = "base"
    base_en = "base.en"
    small = "small"
    small_en = "small.en"
    medium = "medium"
    medium_en = "medium.en"
    large = "large"
    large_v1 = "large-v1"
    large_v2 = "large-v2"
    large_v3 = "large-v3"

class Device(str, Enum):
    cuda = "cuda"
    cpu = "cpu"


class Language(str, Enum):
    def __init__(self):
        for code, name in utils.LANGUAGES.items():
            setattr(Language, code, name)

