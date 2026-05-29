"""Tests for transcript JSON parsing in the audio services API.

Regression coverage for issue #525: the JSON file users download from
``GET /task/{identifier}`` is wrapped in a ``Result`` envelope, and must be
accepted by ``POST /service/align`` without requiring users to manually unwrap
it.
"""

import json

import pytest

from app.api.audio_services_api import _parse_transcript_payload
from app.core.exceptions import ValidationError


BARE_TRANSCRIPT = {
    "language": "en",
    "segments": [
        {"start": 0.0, "end": 1.5, "text": "Hello world."},
    ],
}


def _wrap_as_task_result(transcript: dict) -> dict:
    """Wrap a bare transcript in the envelope returned by ``GET /task/{id}``."""
    return {
        "status": "completed",
        "result": transcript,
        "metadata": {
            "task_type": "transcription",
            "task_params": {},
            "language": transcript.get("language"),
            "file_name": "audio.wav",
            "url": None,
            "callback_url": None,
            "duration": 1.23,
            "audio_duration": 1.5,
            "start_time": "2026-05-19T13:00:00+00:00",
            "end_time": "2026-05-19T13:00:01+00:00",
        },
        "error": None,
    }


@pytest.mark.unit
def test_parse_bare_transcript() -> None:
    """A bare ``{segments, language}`` transcript is parsed unchanged."""
    payload = json.dumps(BARE_TRANSCRIPT).encode("utf-8")

    transcript = _parse_transcript_payload(payload)

    assert transcript.language == "en"
    assert len(transcript.segments) == 1
    assert transcript.segments[0].text == "Hello world."


@pytest.mark.unit
def test_parse_wrapped_task_result_transcript() -> None:
    """A ``GET /task/{id}`` envelope is auto-unwrapped (issue #525)."""
    wrapped = _wrap_as_task_result(BARE_TRANSCRIPT)
    payload = json.dumps(wrapped).encode("utf-8")

    transcript = _parse_transcript_payload(payload)

    assert transcript.language == "en"
    assert len(transcript.segments) == 1
    assert transcript.segments[0].text == "Hello world."


@pytest.mark.unit
def test_parse_invalid_json_raises_validation_error() -> None:
    """Malformed JSON yields a ``INVALID_TRANSCRIPT_JSON`` ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        _parse_transcript_payload(b"not-json{{{")

    assert exc_info.value.code == "INVALID_TRANSCRIPT_JSON"


@pytest.mark.unit
def test_parse_wrapped_with_invalid_inner_result_raises() -> None:
    """A wrapped envelope whose ``result`` is not a valid transcript still raises."""
    wrapped = _wrap_as_task_result({"language": "en"})  # missing segments
    payload = json.dumps(wrapped).encode("utf-8")

    with pytest.raises(ValidationError) as exc_info:
        _parse_transcript_payload(payload)

    assert exc_info.value.code == "INVALID_TRANSCRIPT_JSON"


@pytest.mark.unit
def test_parse_unrecognized_shape_raises() -> None:
    """JSON that matches neither shape raises a clear ValidationError."""
    payload = json.dumps({"foo": "bar"}).encode("utf-8")

    with pytest.raises(ValidationError) as exc_info:
        _parse_transcript_payload(payload)

    assert exc_info.value.code == "INVALID_TRANSCRIPT_JSON"
