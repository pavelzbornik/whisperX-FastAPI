"""This module provides services for processing audio tasks including transcription, diarization, alignment, and speaker assignment using WhisperX and FastAPI."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

import whisperx
from fastapi import HTTPException

from app.core.logging import logger
from app.domain.repositories.task_repository import ITaskRepository
from app.schemas import (
    AlignmentParams,
    ASROptions,
    Device,
    DiarizationParams,
    TaskStatus,
    VADOptions,
    WhisperModelParams,
)
from app.services.whisperx_wrapper_service import (
    align_whisper_output,
    diarize,
    transcribe_with_whisper,
)


def validate_language_code(language_code: str) -> None:
    """
    Validate the language code.

    Args:
        language_code (str): The language code to validate.

    Returns:
        str: The validated language code.
    """
    if language_code not in whisperx.utils.LANGUAGES:
        raise HTTPException(
            status_code=400, detail=f"Invalid language code: {language_code}"
        )


def process_audio_task(
    audio_processor: Callable[..., Any],
    identifier: str,
    task_type: str,
    repository: ITaskRepository,
    *args: Any,
) -> None:
    """
    Process an audio task.

    Args:
        audio_processor (callable): The function to process the audio.
        identifier (str): The task identifier.
        task_type (str): The type of the task.
        repository (ITaskRepository): The task repository.
        *args: Additional arguments for the audio processor.
    """
    try:
        start_time = datetime.now()
        logger.info(f"Starting {task_type} task for identifier {identifier}")

        result = audio_processor(*args)

        if task_type == "diarization":
            result = result.drop(columns=["segment"]).to_dict(orient="records")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"Completed {task_type} task for identifier {identifier}. Duration: {duration}s"
        )

        repository.update(
            identifier=identifier,
            update_data={
                "status": TaskStatus.completed,
                "result": result,
                "duration": duration,
                "start_time": start_time,
                "end_time": end_time,
            },
        )

    except (ValueError, TypeError, RuntimeError) as e:
        logger.error(
            f"Task {task_type} failed for identifier {identifier}. Error: {str(e)}"
        )
        repository.update(
            identifier=identifier,
            update_data={"status": TaskStatus.failed, "error": str(e)},
        )
    except MemoryError as e:
        logger.error(
            f"Task {task_type} failed for identifier {identifier} due to out of memory. Error: {str(e)}"
        )
        repository.update(
            identifier=identifier,
            update_data={"status": TaskStatus.failed, "error": str(e)},
        )


def process_transcribe(
    audio: Any,
    identifier: str,
    model_params: WhisperModelParams,
    asr_options_params: ASROptions,
    vad_options_params: VADOptions,
    repository: ITaskRepository,
) -> None:
    """
    Process a transcription task.

    Args:
        audio: The audio data.
        identifier (str): The task identifier.
        model_params (WhisperModelParams): The model parameters.
        asr_options_params (ASROptions): The ASR options.
        vad_options_params (VADOptions): The VAD options.
        repository (ITaskRepository): The task repository.
    """
    process_audio_task(
        transcribe_with_whisper,
        identifier,
        "transcription",
        repository,
        audio,
        model_params.task.value,
        asr_options_params.model_dump(),
        vad_options_params.model_dump(),
        model_params.language,
        model_params.batch_size,
        model_params.chunk_size,
        model_params.model,
        model_params.device,
        model_params.device_index,
        model_params.compute_type,
        model_params.threads,
    )


def process_diarize(
    audio: Any,
    identifier: str,
    device: Device,
    diarize_params: DiarizationParams,
    repository: ITaskRepository,
) -> None:
    """
    Process a diarization task.

    Args:
        audio: The audio data.
        identifier (str): The task identifier.
        device (Device): The device to use.
        diarize_params (DiarizationParams): The diarization parameters.
        repository (ITaskRepository): The task repository.
    """
    process_audio_task(
        diarize,
        identifier,
        "diarization",
        repository,
        audio,
        device,
        diarize_params.min_speakers,
        diarize_params.max_speakers,
    )


def process_alignment(
    audio: Any,
    transcript: dict[str, Any],
    identifier: str,
    device: Device,
    align_params: AlignmentParams,
    repository: ITaskRepository,
) -> None:
    """
    Process a transcription alignment task.

    Args:
        audio: The audio data.
        transcript: The transcript data.
        identifier (str): The task identifier.
        device (Device): The device to use.
        align_params (AlignmentParams): The alignment parameters.
        repository (ITaskRepository): The task repository.
    """
    process_audio_task(
        align_whisper_output,
        identifier,
        "transcription_alignment",
        repository,
        transcript["segments"],
        audio,
        transcript["language"],
        device,
        align_params.align_model,
        align_params.interpolate_method,
        align_params.return_char_alignments,
    )


def process_speaker_assignment(
    diarization_segments: Any,
    transcript: dict[str, Any],
    identifier: str,
    repository: ITaskRepository,
) -> None:
    """
    Process a speaker assignment task.

    Args:
        diarization_segments: The diarization segments.
        transcript: The transcript data.
        identifier (str): The task identifier.
        repository (ITaskRepository): The task repository.
    """
    process_audio_task(
        whisperx.assign_word_speakers,
        identifier,
        "combine_transcript&diarization",
        repository,
        diarization_segments,
        transcript,
    )
