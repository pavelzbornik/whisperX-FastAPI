"""Schemas for the OpenAI-compatible audio transcription endpoints."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class OpenAIResponseFormat(str, Enum):
    """Supported OpenAI-compatible response formats."""

    json = "json"
    text = "text"
    srt = "srt"
    verbose_json = "verbose_json"
    vtt = "vtt"


class TimestampGranularity(str, Enum):
    """Supported timestamp granularities for verbose JSON responses."""

    segment = "segment"
    word = "word"


class OpenAITranscriptionRequest(BaseModel):
    """Normalized request payload for OpenAI-compatible transcription endpoints."""

    model: str = Field(description="Model alias or local Whisper checkpoint name")
    language: str | None = Field(
        default=None,
        description="Optional ISO-639-1 language code",
    )
    prompt: str | None = Field(
        default=None,
        description="Optional prompt passed to the ASR initial prompt",
    )
    response_format: OpenAIResponseFormat = Field(
        default=OpenAIResponseFormat.json,
        description="Response format to return",
    )
    temperature: float = Field(
        default=0.0,
        description="Sampling temperature",
    )
    timestamp_granularities: list[TimestampGranularity] = Field(
        default_factory=list,
        description="Timestamp granularities requested for verbose JSON responses",
    )

    @model_validator(mode="after")
    def validate_timestamp_granularities(self) -> "OpenAITranscriptionRequest":
        """Ensure timestamp granularities are only used with verbose JSON output."""
        if (
            self.response_format != OpenAIResponseFormat.verbose_json
            and self.timestamp_granularities
        ):
            raise ValueError(
                "timestamp_granularities[] is only supported when "
                "response_format=verbose_json"
            )
        return self


class OpenAIJsonTranscriptionResponse(BaseModel):
    """JSON response format for OpenAI-compatible transcriptions."""

    text: str


class OpenAIVerboseJsonResponse(BaseModel):
    """Verbose JSON response format for OpenAI-compatible transcriptions."""

    task: str
    language: str | None
    duration: float
    text: str
    segments: list[dict[str, Any]]
    words: list[dict[str, Any]] | None = None
