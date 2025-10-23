"""
This module provides API endpoints for speech-to-text services including transcription.

Alignment, diarization, and combining transcripts with diarization results.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from pydantic import ValidationError

from app.api.dependencies import get_file_service, get_task_repository
from app.audio import get_audio_duration, process_audio_file
from app.core.config import Config
from app.core.logging import logger
from app.domain.entities.task import Task as DomainTask
from app.domain.repositories.task_repository import ITaskRepository
from app.files import ALLOWED_EXTENSIONS
from app.schemas import (
    AlignedTranscription,
    AlignmentParams,
    ASROptions,
    Device,
    DiarizationParams,
    DiarizationSegment,
    Response,
    TaskStatus,
    TaskType,
    Transcript,
    VADOptions,
    WhisperModelParams,
)
from app.services import (
    process_alignment,
    process_diarize,
    process_speaker_assignment,
    process_transcribe,
)
from app.services.file_service import FileService
from app.transcript import filter_aligned_transcription

service_router = APIRouter()


@service_router.post(
    "/service/transcribe",
    tags=["Speech-2-Text services"],
    name="1. Transcribe",
)
async def transcribe(
    background_tasks: BackgroundTasks,
    model_params: WhisperModelParams = Depends(),
    asr_options_params: ASROptions = Depends(),
    vad_options_params: VADOptions = Depends(),
    file: UploadFile = File(..., description="Audio/video file to transcribe"),
    repository: ITaskRepository = Depends(get_task_repository),
    file_service: FileService = Depends(get_file_service),
) -> Response:
    """
    Transcribe an uploaded audio file.

    Args:
        background_tasks (BackgroundTasks): Background tasks dependency.
        model_params (WhisperModelParams): Whisper model parameters.
        asr_options_params (ASROptions): ASR options parameters.
        vad_options_params (VADOptions): VAD options parameters.
        file (UploadFile): Uploaded audio file.
        repository (ITaskRepository): Task repository dependency.
        file_service (FileService): File service dependency.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info("Received transcription request for file: %s", file.filename)

    # Validate and save file using file service
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Filename is missing")

    file_service.validate_file_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = file_service.save_upload(file)
    audio = process_audio_file(temp_file)

    # Create domain task
    task = DomainTask(
        uuid=str(uuid4()),
        status=TaskStatus.processing,
        file_name=file.filename,
        audio_duration=get_audio_duration(audio),
        language=model_params.language,
        task_type=TaskType.transcription,
        task_params={
            **model_params.model_dump(),
            "asr_options": asr_options_params.model_dump(),
            "vad_options": vad_options_params.model_dump(),
        },
        start_time=datetime.now(tz=timezone.utc),
    )

    identifier = repository.add(task)

    background_tasks.add_task(
        process_transcribe,
        audio,
        identifier,
        model_params,
        asr_options_params,
        vad_options_params,
    )

    logger.info("Background task scheduled for processing: ID %s", identifier)
    return Response(identifier=identifier, message="Task queued")


@service_router.post(
    "/service/align",
    tags=["Speech-2-Text services"],
    name="2. Align Transcript",
)
def align(
    background_tasks: BackgroundTasks,
    transcript: UploadFile = File(
        ..., description="Whisper style transcript json file"
    ),
    file: UploadFile = File(
        ..., description="Audio/video file which has been transcribed"
    ),
    device: Device = Query(
        default=Config.DEVICE,
        description="Device to use for PyTorch inference",
    ),
    align_params: AlignmentParams = Depends(),
    repository: ITaskRepository = Depends(get_task_repository),
    file_service: FileService = Depends(get_file_service),
) -> Response:
    """
    Align a transcript with an audio file.

    Args:
        background_tasks (BackgroundTasks): Background tasks dependency.
        transcript (UploadFile): Uploaded transcript file.
        file (UploadFile): Uploaded audio file.
        device (Device): Device for PyTorch inference.
        align_params (AlignmentParams): Alignment parameters.
        repository (ITaskRepository): Task repository dependency.
        file_service (FileService): File service dependency.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info(
        "Received alignment request for file: %s and transcript: %s",
        file.filename,
        transcript.filename,
    )

    # Validate transcript file
    if transcript.filename is None:
        raise HTTPException(status_code=400, detail="Transcript filename is missing")

    file_service.validate_file_extension(transcript.filename, {".json"})

    try:
        # Read the content of the transcript file
        transcript_data = Transcript(**json.loads(transcript.file.read()))
    except ValidationError as e:
        logger.error("Invalid JSON content in transcript file: %s", str(e))
        raise HTTPException(status_code=400, detail=f"Invalid JSON content. {str(e)}")

    # Validate and save audio file
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Audio filename is missing")

    file_service.validate_file_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = file_service.save_upload(file)
    audio = process_audio_file(temp_file)

    # Create domain task
    task = DomainTask(
        uuid=str(uuid4()),
        status=TaskStatus.processing,
        file_name=file.filename,
        audio_duration=get_audio_duration(audio),
        language=transcript_data.language,
        task_type=TaskType.transcription_alignment,
        task_params={
            **align_params.model_dump(),
            "device": device,
        },
        start_time=datetime.now(tz=timezone.utc),
    )

    identifier = repository.add(task)

    background_tasks.add_task(
        process_alignment,
        audio,
        transcript_data.model_dump(),
        identifier,
        device,
        align_params,
    )

    logger.info("Background task scheduled for processing: ID %s", identifier)
    return Response(identifier=identifier, message="Task queued")


@service_router.post(
    "/service/diarize", tags=["Speech-2-Text services"], name="3. Diarize"
)
async def diarize(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    repository: ITaskRepository = Depends(get_task_repository),
    device: Device = Query(
        default=Config.DEVICE,
        description="Device to use for PyTorch inference",
    ),
    diarize_params: DiarizationParams = Depends(),
    file_service: FileService = Depends(get_file_service),
) -> Response:
    """
    Perform diarization on an uploaded audio file.

    Args:
        background_tasks (BackgroundTasks): Background tasks dependency.
        file (UploadFile): Uploaded audio file.
        repository (ITaskRepository): Task repository dependency.
        device (Device): Device for PyTorch inference.
        diarize_params (DiarizationParams): Diarization parameters.
        file_service (FileService): File service dependency.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info("Received diarization request for file: %s", file.filename)

    # Validate and save file using file service
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Filename is missing")

    file_service.validate_file_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = file_service.save_upload(file)
    audio = process_audio_file(temp_file)

    # Create domain task
    task = DomainTask(
        uuid=str(uuid4()),
        status=TaskStatus.processing,
        file_name=file.filename,
        audio_duration=get_audio_duration(audio),
        task_type=TaskType.diarization,
        task_params={
            **diarize_params.model_dump(),
            "device": device,
        },
        start_time=datetime.now(tz=timezone.utc),
    )

    identifier = repository.add(task)

    background_tasks.add_task(
        process_diarize,
        audio,
        identifier,
        device,
        diarize_params,
    )

    logger.info("Background task scheduled for processing: ID %s", identifier)
    return Response(identifier=identifier, message="Task queued")


@service_router.post(
    "/service/combine",
    tags=["Speech-2-Text services"],
    name="4. Combine Transcript and Diarization result",
)
async def combine(
    background_tasks: BackgroundTasks,
    aligned_transcript: UploadFile = File(...),
    diarization_result: UploadFile = File(...),
    repository: ITaskRepository = Depends(get_task_repository),
    file_service: FileService = Depends(get_file_service),
) -> Response:
    """
    Combine a transcript with diarization results.

    Args:
        background_tasks (BackgroundTasks): Background tasks dependency.
        aligned_transcript (UploadFile): Uploaded aligned transcript file.
        diarization_result (UploadFile): Uploaded diarization result file.
        repository (ITaskRepository): Task repository dependency.
        file_service (FileService): File service dependency.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info(
        "Received combine request for aligned transcript: %s and diarization result: %s",
        aligned_transcript.filename,
        diarization_result.filename,
    )

    # Validate files
    if aligned_transcript.filename is None:
        raise HTTPException(
            status_code=400, detail="Aligned transcript filename is missing"
        )
    if diarization_result.filename is None:
        raise HTTPException(
            status_code=400, detail="Diarization result filename is missing"
        )

    file_service.validate_file_extension(aligned_transcript.filename, {".json"})
    file_service.validate_file_extension(diarization_result.filename, {".json"})

    try:
        # Read the content of the transcript file
        transcript = AlignedTranscription(**json.loads(aligned_transcript.file.read()))
        # removing words within each segment that have missing start, end, or score values
        transcript = filter_aligned_transcription(transcript)
    except ValidationError as e:
        logger.error("Invalid JSON content in aligned transcript file: %s", str(e))
        raise HTTPException(status_code=400, detail=f"Invalid JSON content. {str(e)}")
    try:
        # Map JSON to list of models
        diarization_segments = []
        for item in json.loads(diarization_result.file.read()):
            diarization_segments.append(DiarizationSegment(**item))
    except ValidationError as e:
        logger.error("Invalid JSON content in diarization result file: %s", str(e))
        raise HTTPException(status_code=400, detail=f"Invalid JSON content. {str(e)}")

    # Create domain task
    task = DomainTask(
        uuid=str(uuid4()),
        status=TaskStatus.processing,
        file_name=None,
        task_type=TaskType.combine_transcript_diarization,
        start_time=datetime.now(tz=timezone.utc),
    )

    identifier = repository.add(task)

    background_tasks.add_task(
        process_speaker_assignment,
        pd.json_normalize([segment.model_dump() for segment in diarization_segments]),
        transcript.model_dump(),
        identifier,
    )

    logger.info("Background task scheduled for processing: ID %s", identifier)
    return Response(identifier=identifier, message="Task queued")
