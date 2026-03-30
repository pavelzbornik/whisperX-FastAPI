"""Pydantic schemas for speaker embedding API endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateSpeakerRequest(BaseModel):
    """Request schema for creating a speaker embedding."""

    speaker_label: str = Field(description="User-facing name for the speaker")
    embedding: list[float] = Field(description="Speaker embedding vector")
    description: str | None = Field(
        default=None, description="Free-text description (role, voice notes, etc.)"
    )
    task_uuid: str | None = Field(
        default=None, description="Optional link to originating diarization task"
    )


class UpdateSpeakerRequest(BaseModel):
    """Request schema for updating a speaker embedding."""

    speaker_label: str | None = Field(default=None, description="Updated speaker name")
    description: str | None = Field(default=None, description="Updated description")
    embedding: list[float] | None = Field(
        default=None, description="Updated embedding vector"
    )


class SpeakerResponse(BaseModel):
    """Response schema for a speaker embedding."""

    model_config = ConfigDict(from_attributes=True)

    uuid: str
    task_uuid: str | None
    speaker_label: str
    description: str | None
    embedding: list[float]
    created_at: datetime


class SpeakerSearchRequest(BaseModel):
    """Request schema for searching similar speakers."""

    embedding: list[float] = Field(description="Query embedding vector")
    limit: int = Field(default=5, ge=1, le=100, description="Max results to return")
    threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold",
    )


class SpeakerIdentifyRequest(BaseModel):
    """Request schema for identifying a speaker."""

    embedding: list[float] = Field(description="Query embedding vector")
    threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold",
    )


class SpeakerSearchResult(BaseModel):
    """A single search result with similarity score."""

    speaker: SpeakerResponse
    similarity: float


class SpeakerSearchResponse(BaseModel):
    """Response schema for speaker search."""

    results: list[SpeakerSearchResult]
