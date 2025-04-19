"""This module provides services for processing audio tasks including transcription, diarization, alignment, and speaker assignment using WhisperX and FastAPI."""

from datetime import datetime

import whisperx
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db_session
from .logger import logger  # Import the logger from the new module
from .schemas import (
    AlignmentParams,
    ASROptions,
    DiarizationParams,
    VADOptions,
    WhisperModelParams,
)
from .tasks import update_task_status_in_db
from .whisperx_services import align_whisper_output, diarize, transcribe_with_whisper


def validate_language_code(language_code):
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
    audio_processor,
    identifier: str,
    task_type: str,
    session: Session = Depends(get_db_session),
    *args,
):
    """
    Process an audio task.

    Args:
        audio_processor (callable): The function to process the audio.
        identifier (str): The task identifier.
        task_type (str): The type of the task.
        session (Session): The database session.
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

        update_task_status_in_db(
            identifier=identifier,
            update_data={
                "status": "completed",
                "result": result,
                "duration": duration,
                "start_time": start_time,
                "end_time": end_time,
            },
            session=session,
        )

    except (ValueError, TypeError, RuntimeError) as e:
        logger.error(
            f"Task {task_type} failed for identifier {identifier}. Error: {str(e)}"
        )
        update_task_status_in_db(
            identifier=identifier,
            update_data={"status": "failed", "error": str(e)},
            session=session,
        )
    except MemoryError as e:
        logger.error(
            f"Task {task_type} failed for identifier {identifier} due to out of memory. Error: {str(e)}"
        )
        update_task_status_in_db(
            identifier=identifier,
            update_data={"status": "failed", "error": str(e)},
            session=session,
        )


def process_transcribe(
    audio,
    identifier,
    model_params: WhisperModelParams,
    asr_options_params: ASROptions,
    vad_options_params: VADOptions,
    session: Session = Depends(get_db_session),
):
    """
    Process a transcription task.

    Args:
        audio: The audio data.
        identifier (str): The task identifier.
        model_params (WhisperModelParams): The model parameters.
        asr_options_params (ASROptions): The ASR options.
        vad_options_params (VADOptions): The VAD options.
        session (Session): The database session.
    """
    process_audio_task(
        transcribe_with_whisper,
        identifier,
        "transcription",
        session,
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
    audio,
    identifier,
    device,
    diarize_params: DiarizationParams,
    session: Session = Depends(get_db_session),
):
    """
    Process a diarization task.

    Args:
        audio: The audio data.
        identifier (str): The task identifier.
        device: The device to use.
        diarize_params (DiarizationParams): The diarization parameters.
        session (Session): The database session.
    """
    process_audio_task(
        diarize,
        identifier,
        "diarization",
        session,
        audio,
        device,
        diarize_params.min_speakers,
        diarize_params.max_speakers,
    )


def process_alignment(
    audio,
    transcript,
    identifier,
    device,
    align_params: AlignmentParams,
    session: Session = Depends(get_db_session),
):
    """
    Process a transcription alignment task.

    Args:
        audio: The audio data.
        transcript: The transcript data.
        identifier (str): The task identifier.
        device: The device to use.
        align_params (AlignmentParams): The alignment parameters.
        session (Session): The database session.
    """
    process_audio_task(
        align_whisper_output,
        identifier,
        "transcription_alignment",
        session,
        transcript["segments"],
        audio,
        transcript["language"],
        device,
        align_params.align_model,
        align_params.interpolate_method,
        align_params.return_char_alignments,
    )


def process_speaker_assignment(
    diarization_segments,
    transcript,
    identifier,
    session: Session = Depends(get_db_session),
):
    """
    Process a speaker assignment task.

    Args:
        diarization_segments: The diarization segments.
        transcript: The transcript data.
        identifier (str): The task identifier.
        session (Session): The database session.
    """
    process_audio_task(
        whisperx.assign_word_speakers,
        identifier,
        "combine_transcript&diarization",
        session,
        diarization_segments,
        transcript,
    )
