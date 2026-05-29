"""Unit tests for OpenAI-compatible request mapping."""

import pytest

from app.api.mappers import map_request_to_whisper_params, resolve_openai_model
from app.api.schemas import OpenAITranscriptionRequest
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.schemas import TaskEnum


@pytest.mark.unit
def test_resolve_openai_model_alias_uses_configured_default() -> None:
    """The whisper-1 alias should map to the configured local checkpoint."""
    settings = get_settings()

    assert resolve_openai_model("whisper-1", settings) == settings.whisper.WHISPER_MODEL


@pytest.mark.unit
def test_map_request_to_whisper_params_maps_prompt_and_temperature() -> None:
    """OpenAI request fields should map to WhisperX model and ASR parameters."""
    settings = get_settings()
    request = OpenAITranscriptionRequest(
        model="whisper-1",
        language="en",
        prompt="Context prompt",
        temperature=0.4,
    )

    model_params, asr_options = map_request_to_whisper_params(
        openai_request=request,
        task=TaskEnum.TRANSCRIBE,
        settings=settings,
    )

    assert model_params.model == settings.whisper.WHISPER_MODEL
    assert model_params.task == TaskEnum.TRANSCRIBE
    assert model_params.language == "en"
    assert asr_options.initial_prompt == "Context prompt"
    assert asr_options.temperatures == [0.4]


@pytest.mark.unit
def test_map_request_to_whisper_params_rejects_unknown_model() -> None:
    """Unknown model aliases should raise a validation error."""
    settings = get_settings()
    request = OpenAITranscriptionRequest(model="unknown-model", language="en")

    with pytest.raises(ValidationError):
        map_request_to_whisper_params(
            openai_request=request,
            task=TaskEnum.TRANSCRIBE,
            settings=settings,
        )
