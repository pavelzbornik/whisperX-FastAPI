"""Retry behaviour of the speech-to-text pipeline runner.

The pipeline runner differs from the generic task runner in one important way:
it posts a callback when it is done. That callback must fire once for the task,
not once per attempt.
"""

import os
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.core.config import get_settings
from app.core.exceptions import InsufficientMemoryError
from app.domain.entities.task import Task
from app.schemas import (
    AlignmentParams,
    ASROptions,
    ComputeType,
    Device,
    DiarizationParams,
    InterpolateMethod,
    SpeechToTextProcessingParams,
    TaskEnum,
    TaskStatus,
    VADOptions,
    WhisperModel,
    WhisperModelParams,
)
from app.services import whisperx_wrapper_service

_ENV_KEYS = ("TASK_MAX_RETRIES", "TASK_RETRY_BACKOFF_SECONDS")


@pytest.fixture(autouse=True)
def reset_retry_env() -> Generator[None, None, None]:
    """Restore retry env vars and the settings cache around each test."""
    get_settings.cache_clear()
    originals = {key: os.environ.get(key) for key in _ENV_KEYS}
    yield
    for key, value in originals.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


def _params(callback_url: str | None) -> SpeechToTextProcessingParams:
    """Build minimal CPU pipeline parameters."""
    return SpeechToTextProcessingParams(
        audio=np.zeros(16000, dtype=np.float32),
        identifier="task-1",
        callback_url=callback_url,
        whisper_model_params=WhisperModelParams(
            language="en",
            model=WhisperModel.tiny,
            device=Device.cpu,
            device_index=0,
            compute_type=ComputeType.int8,
            task=TaskEnum.TRANSCRIBE,
            threads=0,
            batch_size=8,
            chunk_size=20,
        ),
        asr_options=ASROptions(
            beam_size=5,
            best_of=5,
            patience=1,
            length_penalty=1,
            temperatures=[0.0],
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
            initial_prompt=None,
            suppress_tokens=[-1],
            suppress_numerals=True,
            hotwords=None,
        ),
        vad_options=VADOptions(vad_onset=0.5, vad_offset=0.363),
        alignment_params=AlignmentParams(
            align_model=None,
            interpolate_method=InterpolateMethod.nearest,
            return_char_alignments=False,
        ),
        diarization_params=DiarizationParams(min_speakers=1, max_speakers=2),
    )


def _run(
    *,
    max_retries: str,
    callback_url: str | None = None,
) -> tuple[MagicMock, MagicMock, list[dict[str, Any]]]:
    """Run the pipeline with a transcription service that always fails."""
    os.environ["TASK_MAX_RETRIES"] = max_retries
    os.environ["TASK_RETRY_BACKOFF_SECONDS"] = "0.01"
    get_settings.cache_clear()

    updates: list[dict[str, Any]] = []
    repository = MagicMock()
    repository.update.side_effect = lambda identifier, update_data: updates.append(
        update_data
    )
    # A real entity: the callback path builds a pydantic Metadata from it, so a
    # bare MagicMock would not survive validation.
    repository.get_by_id.return_value = Task(
        uuid="task-1",
        status=TaskStatus.failed.value,
        task_type="full_process",
    )

    transcription = MagicMock()
    transcription.transcribe.side_effect = InsufficientMemoryError("transcription")

    callback = MagicMock()

    with (
        patch.object(whisperx_wrapper_service, "SyncSessionLocal", MagicMock()),
        patch.object(
            whisperx_wrapper_service,
            "SyncSQLAlchemyTaskRepository",
            return_value=repository,
        ),
        patch.object(whisperx_wrapper_service.time, "sleep", MagicMock()),
        patch.object(whisperx_wrapper_service, "post_task_callback", callback),
    ):
        whisperx_wrapper_service.process_audio_common(
            _params(callback_url),
            transcription_service=transcription,
        )

    return transcription, callback, updates


@pytest.mark.unit
def test_transient_failure_is_retried() -> None:
    """A transient transcription failure consumes the retry budget."""
    transcription, _, updates = _run(max_retries="2")

    assert transcription.transcribe.call_count == 3
    assert updates[-1]["status"] == TaskStatus.failed
    assert updates[-1]["retry_count"] == 2


@pytest.mark.unit
def test_no_retry_when_disabled() -> None:
    """Default configuration keeps the previous single-attempt behaviour."""
    transcription, _, updates = _run(max_retries="0")

    assert transcription.transcribe.call_count == 1
    assert updates[-1]["status"] == TaskStatus.failed


@pytest.mark.unit
def test_callback_fires_once_despite_retries() -> None:
    """The caller is notified once, after the final attempt.

    Firing per attempt would spam the caller with interim failures for a task
    that may still succeed.
    """
    transcription, callback, _ = _run(
        max_retries="2", callback_url="http://example.com/hook"
    )

    assert transcription.transcribe.call_count == 3
    assert callback.call_count == 1


@pytest.mark.unit
def test_no_callback_when_none_configured() -> None:
    """Tasks without a callback URL still complete their retries cleanly."""
    transcription, callback, _ = _run(max_retries="1", callback_url=None)

    assert transcription.transcribe.call_count == 2
    assert callback.call_count == 0
