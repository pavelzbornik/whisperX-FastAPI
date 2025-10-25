"""
This module contains the FastAPI routes for speech-to-text processing.

It includes endpoints for processing uploaded audio files and audio files from URLs.
"""

import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    UploadFile,
)
from opentelemetry import context, trace

from app.api.dependencies import get_file_service, get_task_repository
from app.audio import get_audio_duration, process_audio_file
from app.core.exceptions import FileValidationError
from app.core.logging import logger
from app.domain.entities.task import Task as DomainTask
from app.domain.repositories.task_repository import ITaskRepository
from app.files import ALLOWED_EXTENSIONS
from app.observability.metrics import get_metrics
from app.observability.tracing import get_tracer
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
from app.services.file_service import FileService


# Configure logging
logging.basicConfig(level=logging.INFO)

# Get tracer and metrics
tracer = get_tracer(__name__)
metrics = get_metrics()

stt_router = APIRouter()


@stt_router.post("/speech-to-text", tags=["Speech-2-Text"])
async def speech_to_text(
    background_tasks: BackgroundTasks,
    model_params: WhisperModelParams = Depends(),
    align_params: AlignmentParams = Depends(),
    diarize_params: DiarizationParams = Depends(),
    asr_options_params: ASROptions = Depends(),
    vad_options_params: VADOptions = Depends(),
    file: UploadFile = File(...),
    repository: ITaskRepository = Depends(get_task_repository),
    file_service: FileService = Depends(get_file_service),
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
        repository (ITaskRepository): Task repository dependency.
        file_service (FileService): File service dependency.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info("Received file upload request: %s", file.filename)

    # Validate file using file service
    if file.filename is None:
        raise FileValidationError(filename="unknown", reason="Filename is missing")

    with tracer.start_as_current_span(
        "audio.validate_and_save",
        attributes={"file.name": file.filename},
    ) as span:
        file_service.validate_file_extension(file.filename, ALLOWED_EXTENSIONS)

        # Save file using file service
        temp_file = file_service.save_upload(file)
        logger.info("%s saved as temporary file: %s", file.filename, temp_file)

        # Get file size
        file_size = os.path.getsize(temp_file)
        span.set_attributes(
            {
                "file.size_bytes": file_size,
                "file.path": temp_file,
            }
        )
        span.add_event("file_uploaded", {"filename": file.filename})

        # Record file size metric
        metrics.audio_file_size_bytes.record(file_size)

    # Process audio
    with tracer.start_as_current_span("audio.load_and_validate") as span:
        audio = process_audio_file(temp_file)
        audio_duration = get_audio_duration(audio)
        logger.info("Audio file %s length: %s seconds", file.filename, audio_duration)

        span.set_attributes(
            {
                "audio.duration_seconds": audio_duration,
                "audio.filename": file.filename,
            }
        )

        # Record audio duration metric
        metrics.audio_duration_seconds.record(audio_duration)

    # Create domain task
    task = DomainTask(
        uuid=str(uuid4()),
        status=TaskStatus.processing,
        file_name=file.filename,
        audio_duration=audio_duration,
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
    )

    identifier = repository.add(task)
    logger.info("Task added to database: ID %s", identifier)

    # Get current trace context to propagate to background task
    trace_context = context.get_current()

    audio_params = SpeechToTextProcessingParams(
        audio=audio,
        identifier=identifier,
        vad_options=vad_options_params,
        asr_options=asr_options_params,
        whisper_model_params=model_params,
        alignment_params=align_params,
        diarization_params=diarize_params,
    )

    # Add trace context to background task
    background_tasks.add_task(process_audio_common, audio_params, trace_context)
    logger.info("Background task scheduled for processing: ID %s", identifier)

    # Add event to span
    current_span = trace.get_current_span()
    if current_span.is_recording():
        current_span.add_event(
            "task_queued",
            {
                "task_id": identifier,
                "task_type": TaskType.full_process.value,
                "audio_duration_seconds": audio_duration,
            },
        )

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
    repository: ITaskRepository = Depends(get_task_repository),
    file_service: FileService = Depends(get_file_service),
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
        repository (ITaskRepository): Task repository dependency.
        file_service (FileService): File service dependency.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info("Received URL for processing: %s", url)

    # Download file using file service
    temp_audio_file, filename = file_service.download_from_url(url)
    logger.info("File downloaded and saved temporarily: %s", temp_audio_file)

    # Validate extension
    file_service.validate_file_extension(temp_audio_file, ALLOWED_EXTENSIONS)

    # Process audio
    audio = process_audio_file(temp_audio_file)
    logger.info("Audio file processed: duration %s seconds", get_audio_duration(audio))

    # Create domain task
    task = DomainTask(
        uuid=str(uuid4()),
        status=TaskStatus.processing,
        file_name=filename,
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
    )

    identifier = repository.add(task)
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

    background_tasks.add_task(process_audio_common, audio_params)
    logger.info("Background task scheduled for processing: ID %s", identifier)

    return Response(identifier=identifier, message="Task queued")
