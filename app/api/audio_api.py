"""
This module contains the FastAPI routes for speech-to-text processing.

It includes endpoints for processing uploaded audio files and audio files from URLs.
"""

import logging
import os
import re
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile

import requests
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.audio import get_audio_duration, process_audio_file
from app.core.logging import logger
from app.files import ALLOWED_EXTENSIONS, save_temporary_file, validate_extension
from app.infrastructure.database import add_task_to_db, get_db_session
from app.schemas import (
    AlignmentParams,
    ASROptions,
    DiarizationParams,
    Response,
    SpeechToTextProcessingParams,
    TaskStatus,
    TaskType,
    VADOptions,
    WhisperModelParams,
)
from app.services import process_audio_common


# Custom secure_filename implementation (no Werkzeug dependency)
def secure_filename(filename: str) -> str:
    """Sanitize the filename to ensure it is safe for use in file systems."""
    filename = os.path.basename(filename)
    # Only allow alphanumerics, dash, underscore, and dot
    filename = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)
    # Replace multiple consecutive dots or underscores with a single underscore
    filename = re.sub(r"[._]{2,}", "_", filename)
    # Remove leading dots or underscores
    filename = re.sub(r"^[._]+", "", filename)
    # Ensure filename is not empty or problematic
    if not filename or filename in {".", ".."}:
        raise ValueError(
            "Filename is empty or contains only special characters after sanitization."
        )
    return filename


# Configure logging
logging.basicConfig(level=logging.INFO)

stt_router = APIRouter()

# Module-level constant for lowercased allowed extensions
ALLOWED_EXTENSIONS_LOWER = {ext.lower() for ext in ALLOWED_EXTENSIONS}


@stt_router.post("/speech-to-text", tags=["Speech-2-Text"])
async def speech_to_text(
    background_tasks: BackgroundTasks,
    model_params: WhisperModelParams = Depends(),
    align_params: AlignmentParams = Depends(),
    diarize_params: DiarizationParams = Depends(),
    asr_options_params: ASROptions = Depends(),
    vad_options_params: VADOptions = Depends(),
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
) -> Response:
    """
    Process an uploaded audio file for speech-to-text conversion.

    Args:
        background_tasks (BackgroundTasks): Background tasks dependency.
        model_params (WhisperModelParams): Whisper model parameters.
        align_params (AlignmentParams): Alignment parameters.
        diarize_params (DiarizationParams): Diarization parameters.
        asr_options_params (ASROptions): ASR options parameters.
        vad_options_params (VADOptions): VAD options parameters.
        file (UploadFile): Uploaded audio file.
        session (Session): Database session dependency.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info("Received file upload request: %s", file.filename)

    if file.filename is None:
        raise HTTPException(status_code=400, detail="Filename is missing")

    validate_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = save_temporary_file(file.file, file.filename)
    logger.info("%s saved as temporary file: %s", file.filename, temp_file)

    audio = process_audio_file(temp_file)
    audio_duration = get_audio_duration(audio)
    logger.info("Audio file %s length: %s seconds", file.filename, audio_duration)

    identifier = add_task_to_db(
        status=TaskStatus.processing,
        file_name=file.filename,
        audio_duration=get_audio_duration(audio),
        language=model_params.language,
        task_type=TaskType.full_process,
        task_params={
            **model_params.model_dump(),
            **align_params.model_dump(),
            "asr_options": asr_options_params.model_dump(),
            "vad_options": vad_options_params.model_dump(),
            **diarize_params.model_dump(),
        },
        start_time=datetime.now(tz=timezone.utc),
        session=session,
    )
    logger.info("Task added to database: ID %s", identifier)

    audio_params = SpeechToTextProcessingParams(
        audio=audio,
        identifier=identifier,
        vad_options=vad_options_params,
        asr_options=asr_options_params,
        whisper_model_params=model_params,
        alignment_params=align_params,
        diarization_params=diarize_params,
    )

    background_tasks.add_task(process_audio_common, audio_params, session)
    logger.info("Background task scheduled for processing: ID %s", identifier)

    return Response(identifier=identifier, message="Task queued")


@stt_router.post("/speech-to-text-url", tags=["Speech-2-Text"])
async def speech_to_text_url(
    background_tasks: BackgroundTasks,
    model_params: WhisperModelParams = Depends(),
    align_params: AlignmentParams = Depends(),
    diarize_params: DiarizationParams = Depends(),
    asr_options_params: ASROptions = Depends(),
    vad_options_params: VADOptions = Depends(),
    url: str = Form(...),
    session: Session = Depends(get_db_session),
) -> Response:
    """
    Process an audio file from a URL for speech-to-text conversion.

    Args:
        background_tasks (BackgroundTasks): Background tasks dependency.
        model_params (WhisperModelParams): Whisper model parameters.
        align_params (AlignmentParams): Alignment parameters.
        diarize_params (DiarizationParams): Diarization parameters.
        asr_options_params (ASROptions): ASR options parameters.
        vad_options_params (VADOptions): VAD options parameters.
        url (str): URL of the audio file.
        session (Session): Database session dependency.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info("Received URL for processing: %s", url)

    # Extract filename from HTTP response headers or URL
    with requests.get(url, stream=True) as response:
        response.raise_for_status()

        # Check for filename in Content-Disposition header
        content_disposition = response.headers.get("Content-Disposition")
        if content_disposition and "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[1].strip('"')
        else:
            # Fall back to extracting from the URL path
            filename = os.path.basename(url)
            filename = secure_filename(filename)  # Sanitize the filename

        # Get the file extension
        _, ext_candidate = os.path.splitext(filename)
        ext_candidate = ext_candidate.lower().strip()  # Normalize and remove whitespace
        # Only allow single extensions that perfectly match allowed values (start with . and followed by alphanum only)
        # Defensive: reconstruct the extension from allowed set if possible
        if not ext_candidate or not ext_candidate.startswith('.'):
            raise ValueError(f"Invalid file extension: {ext_candidate}")
        ext_clean = ext_candidate[1:]  # remove leading dot for lookup
        # Defensive: Only allow usage if clean is in allowed set
        # Use a canonical extension from allowed set (lowercase)
        extension_to_suffix = {ext.lower().lstrip('.'): ext for ext in ALLOWED_EXTENSIONS}
        if ext_clean not in extension_to_suffix:
            raise ValueError(f"Invalid file extension: {ext_candidate}")
        safe_suffix = '.' + ext_clean
        
        # Save the file to a temporary location
        temp_audio_file = NamedTemporaryFile(suffix=safe_suffix, delete=False)
        for chunk in response.iter_content(chunk_size=8192):
            temp_audio_file.write(chunk)

    logger.info("File downloaded and saved temporarily: %s", temp_audio_file.name)
    validate_extension(temp_audio_file.name, ALLOWED_EXTENSIONS)

    audio = process_audio_file(temp_audio_file.name)
    logger.info("Audio file processed: duration %s seconds", get_audio_duration(audio))

    identifier = add_task_to_db(
        status=TaskStatus.processing,
        file_name=temp_audio_file.name,
        audio_duration=get_audio_duration(audio),
        language=model_params.language,
        task_type=TaskType.full_process,
        task_params={
            **model_params.model_dump(),
            **align_params.model_dump(),
            "asr_options": asr_options_params.model_dump(),
            "vad_options": vad_options_params.model_dump(),
            **diarize_params.model_dump(),
        },
        url=url,
        start_time=datetime.now(tz=timezone.utc),
        session=session,
    )
    logger.info("Task added to database: ID %s", identifier)

    audio_params = SpeechToTextProcessingParams(
        audio=audio,
        identifier=identifier,
        vad_options=vad_options_params,
        asr_options=asr_options_params,
        whisper_model_params=model_params,
        alignment_params=align_params,
        diarization_params=diarize_params,
    )

    background_tasks.add_task(process_audio_common, audio_params, session)
    logger.info("Background task scheduled for processing: ID %s", identifier)

    return Response(identifier=identifier, message="Task queued")
