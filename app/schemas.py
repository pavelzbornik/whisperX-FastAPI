from fastapi import Query
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Any
from enum import Enum
from whisperx import utils
import numpy as np
import os

WHISPER_MODEL = os.getenv("WHISPER_MODEL")
LANG = os.getenv("DEFAULT_LANG")


class Response(BaseModel):
    identifier: str
    message: str


class Metadata(BaseModel):
    task_type: str
    task_params: Optional[dict]
    language: Optional[str]
    file_name: Optional[str]
    url: Optional[str]
    duration: Optional[float]
    audio_duration: Optional[float] = None


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
    start: Optional[float] = None
    end: Optional[float] = None
    score: Optional[float] = None


class AlignmentSegment(BaseModel):
    start: float
    end: float
    text: str
    words: List[Word]


class AlignedTranscription(BaseModel):
    segments: List[AlignmentSegment]
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


class TaskEnum(str, Enum):
    transcribe = "transcribe"
    translate = "translate"


class InterpolateMethod(str, Enum):
    nearest = "nearest"
    linear = "linear"
    ignore = "ignore"


class ASROptions(BaseModel):
    beam_size: int = Field(
        Query(
            5,
            description="Number of beams in beam search, only applicable when temperature is zero",
        )
    )
    patience: float = Field(
        Query(
            1.0, description="Optional patience value to use in beam decoding"
        )
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

    @validator("suppress_tokens", pre=True)
    def parse_suppress_tokens(cls, value):
        if isinstance(value, str):
            return [int(x) for x in value.split(",")]
        return value


class VADOptions(BaseModel):
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

    align_model: Optional[str] = Field(
        Query(
            None, description="Name of phoneme-level ASR model to do alignment"
        )
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
    min_speakers: Optional[int] = Field(
        Query(None, description="Minimum number of speakers to in audio file")
    )
    max_speakers: Optional[int] = Field(
        Query(None, description="Maximum number of speakers to in audio file")
    )


class SpeechToTextProcessingParams(BaseModel):
    audio: (
        np.ndarray
    )  # NumPy array containing the audio waveform, float32 dtype
    identifier: str
    vad_options: VADOptions
    asr_options: ASROptions
    whisper_model_params: WhsiperModelParams
    alignment_params: AlignmentParams
    diarization_params: DiarizationParams

    class Config:
        arbitrary_types_allowed = True
