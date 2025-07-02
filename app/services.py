"""This module provides services for processing audio tasks including transcription, diarization, alignment, and speaker assignment using WhisperX and FastAPI."""

import traceback
from datetime import datetime
from typing import Any, Callable

import whisperx
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db_session
from .logger import logger  # Import the logger from the new module
from .schemas import (
    AlignmentParams,
    ASROptions,
    DiarizationParams,
    TaskStatus,
    VADOptions,
    WhisperModelParams,
)
from .tasks import update_task_status_in_db
from .utils import utc_now
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
    audio_processor: Callable,
    identifier: str,
    task_type: str,
    session: Session = Depends(get_db_session),
    *args: Any,
):
    """
    Process an audio task with comprehensive error handling and monitoring.

    Args:
        audio_processor (callable): The function to process the audio.
        identifier (str): The task identifier.
        task_type (str): The type of the task.
        session (Session): The database session.
        *args: Additional arguments for the audio processor.
    """
    start_time = utc_now()
    
    try:
        logger.info(f"Starting {task_type} task for identifier {identifier}")
        
        # Validate inputs
        if not identifier:
            raise ValueError("Task identifier cannot be empty")
        
        if not audio_processor:
            raise ValueError("Audio processor function is required")

        # Execute the audio processing task
        result = audio_processor(*args)

        # Handle different result types
        if task_type == "diarization":
            if hasattr(result, 'drop') and hasattr(result, 'to_dict'):
                result = result.drop(columns=["segment"]).to_dict(orient="records")
            else:
                logger.warning(f"Unexpected diarization result type: {type(result)}")

        end_time = utc_now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(
            f"Completed {task_type} task for identifier {identifier}. Duration: {duration:.2f}s"
        )

        # Update task status in database
        update_task_status_in_db(
            identifier=identifier,
            update_data={
                "status": TaskStatus.completed,
                "result": result,
                "duration": duration,
                "start_time": start_time,
                "end_time": end_time,
            },
            session=session,
        )

    except (ValueError, TypeError) as e:
        duration = (utc_now() - start_time).total_seconds()
        error_msg = f"Validation error in {task_type} task for identifier {identifier}: {str(e)}"
        logger.error(error_msg)
        logger.debug(f"Validation error traceback: {traceback.format_exc()}")
        
        update_task_status_in_db(
            identifier=identifier,
            update_data={
                "status": TaskStatus.failed, 
                "error": error_msg,
                "duration": duration,
                "end_time": utc_now(),
            },
            session=session,
        )
        
    except RuntimeError as e:
        duration = (utc_now() - start_time).total_seconds()
        error_msg = f"Runtime error in {task_type} task for identifier {identifier}: {str(e)}"
        logger.error(error_msg)
        logger.debug(f"Runtime error traceback: {traceback.format_exc()}")
        
        update_task_status_in_db(
            identifier=identifier,
            update_data={
                "status": TaskStatus.failed, 
                "error": error_msg,
                "duration": duration,
                "end_time": utc_now(),
            },
            session=session,
        )
        
    except MemoryError as e:
        duration = (utc_now() - start_time).total_seconds()
        error_msg = f"Out of memory error in {task_type} task for identifier {identifier}: {str(e)}"
        logger.error(error_msg)
        
        update_task_status_in_db(
            identifier=identifier,
            update_data={
                "status": TaskStatus.failed, 
                "error": error_msg,
                "duration": duration,
                "end_time": utc_now(),
            },
            session=session,
        )
        
    except ImportError as e:
        duration = (utc_now() - start_time).total_seconds()
        error_msg = f"Model loading error in {task_type} task for identifier {identifier}: {str(e)}"
        logger.error(error_msg)
        logger.debug(f"Model loading error traceback: {traceback.format_exc()}")
        
        update_task_status_in_db(
            identifier=identifier,
            update_data={
                "status": TaskStatus.failed, 
                "error": error_msg,
                "duration": duration,
                "end_time": utc_now(),
            },
            session=session,
        )
        
    except Exception as e:
        duration = (utc_now() - start_time).total_seconds()
        error_msg = f"Unexpected error in {task_type} task for identifier {identifier}: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        update_task_status_in_db(
            identifier=identifier,
            update_data={
                "status": TaskStatus.failed, 
                "error": error_msg,
                "duration": duration,
                "end_time": utc_now(),
            },
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
