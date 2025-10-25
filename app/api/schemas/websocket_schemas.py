"""WebSocket schema definitions for real-time transcription."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WebSocketEventType(str, Enum):
    """Event types for WebSocket communication."""

    PROPER_SPEECH_START = "proper_speech_start"
    SPEECH_FALSE_DETECTION = "speech_false_detection"
    SPEECH_END = "speech_end"
    TRANSCRIPTION = "transcription"
    ERROR = "error"
    INFO = "info"


class WebSocketMessage(BaseModel):
    """Base model for WebSocket messages."""

    event: WebSocketEventType
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: float | None = None


class TranscriptionResult(BaseModel):
    """Model for transcription result data."""

    text: str
    language: str | None = None
    duration: float | None = None
    segments: list[dict[str, Any]] | None = None


class VADConfig(BaseModel):
    """Configuration for Voice Activity Detection."""

    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Threshold for speech detection (0.0-1.0)",
    )
    min_speech_duration_ms: int = Field(
        default=250, gt=0, description="Minimum speech duration in milliseconds"
    )
    max_speech_duration_s: float = Field(
        default=float("inf"), gt=0, description="Maximum speech duration in seconds"
    )
    min_silence_duration_ms: int = Field(
        default=100, gt=0, description="Minimum silence duration in milliseconds"
    )
    window_size_samples: int = Field(
        default=512, gt=0, description="Window size for VAD in samples"
    )
    speech_pad_ms: int = Field(
        default=30, ge=0, description="Padding around speech segments in milliseconds"
    )
    pre_roll_buffer_ms: int = Field(
        default=300,
        ge=0,
        description="Pre-roll buffer size in milliseconds to avoid truncation",
    )
    min_utterance_length_s: float = Field(
        default=1.5,
        ge=0,
        description="Minimum utterance length in seconds for transcription",
    )


class AudioConfig(BaseModel):
    """Configuration for audio processing."""

    sample_rate: int = Field(default=16000, gt=0, description="Audio sample rate in Hz")
    channels: int = Field(default=1, ge=1, le=2, description="Number of audio channels")
    sample_width: int = Field(
        default=2, ge=1, le=4, description="Sample width in bytes (e.g., 2 for 16-bit)"
    )


class TranscriptionConfig(BaseModel):
    """Configuration for transcription."""

    language: str | None = Field(
        default=None, description="Language code (auto-detect if None)"
    )
    model: str = Field(default="large-v3", description="WhisperX model to use")
    device: str = Field(default="cuda", description="Device to use (cuda or cpu)")
    compute_type: str = Field(
        default="float16", description="Compute type (float16, float32, int8)"
    )
    batch_size: int = Field(default=16, gt=0, description="Batch size for processing")


class WebSocketSessionConfig(BaseModel):
    """Complete configuration for a WebSocket session."""

    vad_config: VADConfig = Field(default_factory=VADConfig)
    audio_config: AudioConfig = Field(default_factory=AudioConfig)
    transcription_config: TranscriptionConfig = Field(
        default_factory=TranscriptionConfig
    )
