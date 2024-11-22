"""This module contains the schema definitions for the WhisperX FastAPI application."""

import os
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

import numpy as np
from fastapi import Query
from pydantic import BaseModel, Field, field_validator
from whisperx import utils

WHISPER_MODEL = os.getenv("WHISPER_MODEL")
LANG = os.getenv("DEFAULT_LANG", "en")


class Response(BaseModel):
    """Response model for API responses."""

    identifier: str
    message: str


class Metadata(BaseModel):
    """Metadata model for task information."""

    task_type: str
    task_params: Optional[dict]
    language: Optional[str]
    file_name: Optional[str]
    url: Optional[str]
    duration: Optional[float]
    audio_duration: Optional[float] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class TaskSimple(BaseModel):
    """Simple task model with basic task information."""

    identifier: str
    status: str
    task_type: str


class ResultTasks(BaseModel):
    """Model for a list of simple tasks."""

    tasks: List[TaskSimple]


class TranscriptionSegment(BaseModel):
    """Model for a segment of transcription."""

    start: float
    end: float
    text: str


class Segment(BaseModel):
    """Model for a segment with optional speaker information."""

    start: float
    end: float
    text: Optional[str]
    speaker: Optional[str]


class Word(BaseModel):
    """Model for a word with optional timing and score information."""

    word: str
    start: Optional[float] = None
    end: Optional[float] = None
    score: Optional[float] = None


class AlignmentSegment(BaseModel):
    """Model for a segment with word alignments."""

    start: float
    end: float
    text: str
    words: List[Word]


class AlignedTranscription(BaseModel):
    """Model for aligned transcription with segments and word segments."""

    segments: List[AlignmentSegment]
    word_segments: List[Word]


class DiarizationSegment(BaseModel):
    """Model for a diarization segment with speaker information."""

    label: str
    speaker: str
    start: float
    end: float


class DiaredTrancript(BaseModel):
    """Model for a diarized transcript with segments."""

    segments: List[Segment]


class Transcript(BaseModel):
    """Model for a transcript with segments and language."""

    segments: List[TranscriptionSegment]
    language: Optional[str]


class TranscriptInput(BaseModel):
    """Input model for a transcript."""

    transcript: Transcript


class Result(BaseModel):
    """Model for a result with status, result data, metadata, and optional error."""

    status: str
    result: Any
    metadata: Metadata
    error: Optional[str]


class ComputeType(str, Enum):
    """Enum for compute types."""

    float16 = "float16"
    float32 = "float32"
    int8 = "int8"


class WhisperModel(str, Enum):
    """Enum for Whisper model types."""

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
    large_v3_turbo = "large-v3-turbo"


class Device(str, Enum):
    """Enum for device types."""

    cuda = "cuda"
    cpu = "cpu"


class TaskEnum(str, Enum):
    """Enum for task types."""

    transcribe = "transcribe"
    translate = "translate"


class InterpolateMethod(str, Enum):
    """Enum for interpolation methods."""

    nearest = "nearest"
    linear = "linear"
    ignore = "ignore"


class ASROptions(BaseModel):
    """Model for ASR options."""

    beam_size: int = Field(
        Query(
            5,
            description="Number of beams in beam search, only applicable when temperature is zero",
        )
    )
    patience: float = Field(
        Query(1.0, description="Optional patience value to use in beam decoding")
    )
    length_penalty: float = Field(
        Query(1.0, description="Optional token length penalty coefficient")
    )
    temperatures: float = Field(
        Query(0.0, description="Temperature to use for sampling")
    )
    compression_ratio_threshold: float = Field(
        Query(
            2.4,
            description="If the gzip compression ratio is higher than this value, treat the decoding as failed",
        )
    )
    log_prob_threshold: float = Field(
        Query(
            -1.0,
            description="If the average log probability is lower than this value, treat the decoding as failed",
        )
    )
    no_speech_threshold: float = Field(
        Query(
            0.6,
            description="If the probability of the token is higher than this value AND the decoding has failed due to `logprob_threshold`, consider the segment as silence",
        )
    )
    initial_prompt: Optional[str] = Field(
        Query(
            None,
            description="Optional text to provide as a prompt for the first window.",
        )
    )
    suppress_tokens: List[int] = Field(
        Query(
            [-1],
            description="Comma-separated list of token ids to suppress during sampling",
        )
    )
    suppress_numerals: Optional[bool] = Field(
        Query(
            False,
            description="Whether to suppress numeric symbols and currency symbols during sampling",
        )
    )

    @field_validator("suppress_tokens", mode="before")
    def parse_suppress_tokens(cls, value):
        """Parse suppress tokens from a comma-separated string of token IDs into a list of integers."""
        if isinstance(value, str):
            return [int(x) for x in value.split(",")]
        return value


class VADOptions(BaseModel):
    """Model for VAD options."""

    vad_onset: float = Field(
        Query(
            0.500,
            description="Onset threshold for VAD (see pyannote.audio), reduce this if speech is not being detected",
        )
    )
    vad_offset: float = Field(
        Query(
            0.363,
            description="Offset threshold for VAD (see pyannote.audio), reduce this if speech is not being detected.",
        )
    )


class WhsiperModelParams(BaseModel):
    """Model for Whisper model parameters."""

    language: str = Field(
        Query(
            default=LANG,
            description="Language to transcribe",
            enum=list(utils.LANGUAGES.keys()),
        )
    )
    task: TaskEnum = Field(
        Query(
            default="transcribe",
            description="Whether to perform X->X speech recognition ('transcribe') or X->English translation ('translate')",
        )
    )
    model: WhisperModel = Field(
        Query(
            default=WHISPER_MODEL,
            description="Name of the Whisper model to use",
        )
    )
    device: Device = Field(
        Query(
            default="cuda",
            description="Device to use for PyTorch inference",
        )
    )
    device_index: int = Field(
        Query(0, description="Device index to use for FasterWhisper inference")
    )
    threads: int = Field(
        Query(
            0,
            description="Number of threads used by torch for CPU inference; supercedes MKL_NUM_THREADS/OMP_NUM_THREADS",
        )
    )
    batch_size: int = Field(
        Query(8, description="The preferred batch size for inference")
    )
    compute_type: ComputeType = Field(
        Query("float16", description="Type of computation")
    )


class AlignmentParams(BaseModel):
    """Model for alignment parameters."""

    align_model: Optional[str] = Field(
        Query(None, description="Name of phoneme-level ASR model to do alignment")
    )
    interpolate_method: InterpolateMethod = Field(
        Query(
            "nearest",
            description="For word .srt, method to assign timestamps to non-aligned words, or merge them into neighboring.",
        )
    )
    return_char_alignments: bool = Field(
        Query(
            False,
            description="Return character-level alignments in the output json file",
        )
    )


class DiarizationParams(BaseModel):
    """Model for diarization parameters."""

    min_speakers: Optional[int] = Field(
        Query(None, description="Minimum number of speakers to in audio file")
    )
    max_speakers: Optional[int] = Field(
        Query(None, description="Maximum number of speakers to in audio file")
    )


class SpeechToTextProcessingParams(BaseModel):
    """Model for speech-to-text processing parameters."""

    audio: np.ndarray  # NumPy array containing the audio waveform, float32 dtype
    identifier: str
    vad_options: VADOptions
    asr_options: ASROptions
    whisper_model_params: WhsiperModelParams
    alignment_params: AlignmentParams
    diarization_params: DiarizationParams

    class Config:
        """Configuration for the SpeechToTextProcessingParams model."""

        arbitrary_types_allowed = True
