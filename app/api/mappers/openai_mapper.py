"""Mapping helpers for OpenAI-compatible audio transcription endpoints."""

from app.api.schemas.openai import OpenAITranscriptionRequest
from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.schemas import ASROptions, TaskEnum, WhisperModel, WhisperModelParams
from app.services.audio_processing_service import validate_language_code


def resolve_openai_model(model_name: str, settings: Settings) -> WhisperModel:
    """Resolve an OpenAI model alias or local checkpoint name to a Whisper model."""
    if model_name == "whisper-1":
        return settings.whisper.WHISPER_MODEL

    try:
        return WhisperModel(model_name)
    except ValueError as exc:
        raise ValidationError(
            message=f"Unsupported model '{model_name}'",
            code="UNSUPPORTED_MODEL",
            user_message=(
                "Unsupported model. Use 'whisper-1' or a local Whisper checkpoint "
                "name supported by this server."
            ),
            model=model_name,
        ) from exc


def map_request_to_whisper_params(
    openai_request: OpenAITranscriptionRequest,
    task: TaskEnum,
    settings: Settings,
) -> tuple[WhisperModelParams, ASROptions]:
    """Convert an OpenAI-compatible request to internal WhisperX parameters."""
    language = openai_request.language or settings.whisper.DEFAULT_LANG
    validate_language_code(language)

    return (
        WhisperModelParams(
            language=language,
            task=task,
            model=resolve_openai_model(openai_request.model, settings),
            device=settings.whisper.DEVICE,
            device_index=0,
            threads=0,
            batch_size=8,
            chunk_size=20,
            compute_type=settings.whisper.COMPUTE_TYPE,
        ),
        ASROptions(
            beam_size=5,
            best_of=5,
            patience=1.0,
            length_penalty=1.0,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
            initial_prompt=openai_request.prompt,
            suppress_tokens=[-1],
            suppress_numerals=False,
            hotwords=None,
            temperatures=[openai_request.temperature],
        ),
    )
