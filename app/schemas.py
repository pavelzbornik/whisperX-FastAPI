"""This module contains the schema definitions for the WhisperX FastAPI application."""

from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from whisperx import utils  # pyright: ignore[reportMissingTypeStubs]


class Response(BaseModel):
    """Response model for API responses."""

    identifier: str
    message: str


class Metadata(BaseModel):
    """Metadata model for task information."""

    task_type: str
    task_params: dict[str, Any] | None
    language: str | None
    file_name: str | None
    url: str | None
    callback_url: str | None
    duration: float | None
    audio_duration: float | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


class TaskSimple(BaseModel):
    """Simple task model with basic task information."""

    identifier: str
    status: str
    task_type: str
    language: str | None
    file_name: str | None
    error: str | None
    url: str | None
    callback_url: str | None
    duration: float | None
    audio_duration: float | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None

    @classmethod
    def from_domain(cls, task: object) -> "TaskSimple":
        """Create TaskSimple from a domain Task entity.

        The domain Task is expected to have attributes matching the fields
        used here (uuid, status, task_type, language, file_name, error, url,
        duration, audio_duration, start_time, end_time).
        """
        return cls(
            identifier=getattr(task, "uuid", ""),
            status=getattr(task, "status", ""),
            task_type=getattr(task, "task_type", ""),
            language=getattr(task, "language", None),
            file_name=getattr(task, "file_name", None),
            error=getattr(task, "error", None),
            url=getattr(task, "url", None),
            callback_url=getattr(task, "callback_url", None),
            duration=getattr(task, "duration", None),
            audio_duration=getattr(task, "audio_duration", None),
            start_time=getattr(task, "start_time", None),
            end_time=getattr(task, "end_time", None),
        )


class ResultTasks(BaseModel):
    """Model for a list of simple tasks."""

    tasks: list[TaskSimple]


class TaskEventReceived(BaseModel):
    """Confirmation that the callback was received."""

    ok: bool


class TranscriptionSegment(BaseModel):
    """Model for a segment of transcription."""

    start: float
    end: float
    text: str


class Segment(BaseModel):
    """Model for a segment with optional speaker information."""

    start: float
    end: float
    text: str | None
    speaker: str | None


class Word(BaseModel):
    """Model for a word with optional timing and score information."""

    word: str
    start: float | None = None
    end: float | None = None
    score: float | None = None


class AlignmentSegment(BaseModel):
    """Model for a segment with word alignments."""

    start: float
    end: float
    text: str
    words: list[Word]


class AlignedTranscription(BaseModel):
    """Model for aligned transcription with segments and word segments."""

    segments: list[AlignmentSegment]
    word_segments: list[Word]


class DiarizationSegment(BaseModel):
    """Model for a diarization segment with speaker information."""

    label: str
    speaker: str
    start: float
    end: float


class DiarizedTranscript(BaseModel):
    """Model for a diarized transcript with segments."""

    segments: list[Segment]


class Transcript(BaseModel):
    """Model for a transcript with segments and language."""

    segments: list[TranscriptionSegment]
    language: str | None


class TranscriptInput(BaseModel):
    """Input model for a transcript."""

    transcript: Transcript


class Result(BaseModel):
    """Model for a result with status, result data, metadata, and optional error."""

    status: str
    result: Any
    metadata: Metadata
    error: str | None


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
    distil_large_v2 = "distil-large-v2"
    distil_medium_en = "distil-medium.en"
    distil_small_en = "distil-small.en"
    distil_large_v3 = "distil-large-v3"
    faster_crisper_whisper = "nyrahealth/faster_CrisperWhisper"


class Device(str, Enum):
    """Enum for device types."""

    cuda = "cuda"
    cpu = "cpu"


class TaskEnum(str, Enum):
    """Enum for task types."""

    TRANSCRIBE = "transcribe"
    TRANSLATE = "translate"


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
    best_of: int = Field(
        Query(
            5,
            description="Number of beams to keep in beam search, only applicable when temperature is zero",
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
    initial_prompt: str | None = Field(
        Query(
            None,
            description="Optional text to provide as a prompt for the first window.",
        )
    )
    suppress_tokens: list[int] = Field(
        Query(
            [-1],
            description="Comma-separated list of token ids to suppress during sampling",
        )
    )
    suppress_numerals: bool | None = Field(
        Query(
            False,
            description="Whether to suppress numeric symbols and currency symbols during sampling",
        )
    )
    hotwords: str | None = Field(
        Query(
            None,
            description="Hotwords related prompt applied before each transcription window",
        )
    )

    @field_validator("suppress_tokens", mode="before")
    @classmethod
    def parse_suppress_tokens(cls, value: str | list[int]) -> list[int]:
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


class WhisperModelParams(BaseModel):
    """Model for Whisper model parameters."""

    language: str = Field(
        Query(
            default="en",  # Default language
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
            default="tiny",  # Default model
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
            description="Number of threads used by torch for CPU inference; supersedes MKL_NUM_THREADS/OMP_NUM_THREADS",
        )
    )
    batch_size: int = Field(
        Query(8, description="The preferred batch size for inference")
    )
    chunk_size: int = Field(
        Query(
            20,
            description="Chunk size for merging VAD segments. Default is 20, reduce this if the chunk is too long.",
        )
    )
    compute_type: ComputeType = Field(
        Query("float16", description="Type of computation")
    )


class AlignmentParams(BaseModel):
    """Model for alignment parameters."""

    align_model: str | None = Field(
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

    min_speakers: int | None = Field(
        Query(None, description="Minimum number of speakers to in audio file")
    )
    max_speakers: int | None = Field(
        Query(None, description="Maximum number of speakers to in audio file")
    )


class SpeechToTextProcessingParams(BaseModel):
    """Model for speech-to-text processing parameters."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    audio: np.ndarray  # NumPy array containing the audio waveform, float32 dtype
    identifier: str
    vad_options: VADOptions
    asr_options: ASROptions
    whisper_model_params: WhisperModelParams
    alignment_params: AlignmentParams
    diarization_params: DiarizationParams
    callback_url: str | None = None


class TaskType(str, Enum):
    """Enum for task types."""

    transcription = "transcription"
    transcription_alignment = "transcription_alignment"
    diarization = "diarization"
    combine_transcript_diarization = "combine_transcript&diarization"
    full_process = "full_process"


class TaskStatus(str, Enum):
    """Enum for task status."""

    processing = "processing"
    completed = "completed"
    failed = "failed"


class TaskStatus(str, Enum):
    """Enum for task status."""

    processing = "processing"
    completed = "completed"
    failed = "failed"
