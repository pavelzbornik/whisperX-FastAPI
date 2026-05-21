"""Unit tests for OpenAI-compatible API schemas."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.api.schemas import (
    OpenAIResponseFormat,
    OpenAITranscriptionRequest,
    TimestampGranularity,
)


@pytest.mark.unit
def test_openai_transcription_request_defaults() -> None:
    """Default OpenAI request values should be applied."""
    request = OpenAITranscriptionRequest(model="whisper-1")

    assert request.response_format == OpenAIResponseFormat.json
    assert request.temperature == 0.0
    assert request.timestamp_granularities == []


@pytest.mark.unit
def test_timestamp_granularities_require_verbose_json() -> None:
    """Timestamp granularities should be rejected for non-verbose responses."""
    with pytest.raises(PydanticValidationError):
        OpenAITranscriptionRequest(
            model="whisper-1",
            response_format=OpenAIResponseFormat.json,
            timestamp_granularities=[TimestampGranularity.word],
        )
