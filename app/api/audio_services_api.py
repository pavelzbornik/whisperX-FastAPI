"""
This module provides API endpoints for speech-to-text services including transcription.

Alignment, diarization, and combining transcripts with diarization results.
"""

import json
from typing import Annotated
from uuid import uuid4

import pandas as pd
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Query,
    UploadFile,
)
from pydantic import ValidationError as PydanticValidationError

from app.api.constants import (
    JSON_EXTENSION,
    TASK_QUEUED_MESSAGE,
    TASK_SCHEDULED_LOG_FORMAT,
)
from app.api.dependencies import (
    AlignmentServiceDependency,
    DiarizationServiceDependency,
    FileServiceDependency,
    SpeakerAssignmentServiceDependency,
    TaskRepositoryDependency,
    TranscriptionServiceDependency,
)
from app.audio import get_audio_duration, process_audio_file
from app.core.config import Config
from app.core.exceptions import FileValidationError, ValidationError
from app.core.logging import logger
from app.domain.entities.task import Task as DomainTask
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
from app.transcript import filter_aligned_transcription

service_router = APIRouter()


@service_router.post(
    "/service/transcribe",
    tags=["Speech-2-Text services"],
    name="1. Transcribe",
)
async def transcribe(
    background_tasks: BackgroundTasks,
    model_params: Annotated[WhisperModelParams, Depends()],
    asr_options_params: Annotated[ASROptions, Depends()],
    vad_options_params: Annotated[VADOptions, Depends()],
    repository: TaskRepositoryDependency,
    file_service: FileServiceDependency,
    transcription_service: TranscriptionServiceDependency,
    file: UploadFile = File(..., description="Audio/video file to transcribe"),
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
        transcription_service (ITranscriptionService): Transcription service dependency.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info("Received transcription request for file: %s", file.filename)

    # Validate and save file using file service
    if file.filename is None:
        raise FileValidationError(filename="unknown", reason="Filename is missing")

    file_service.validate_file_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = file_service.save_upload(file)
    audio = process_audio_file(temp_file)

    # Create domain task
    task = DomainTask(
        uuid=str(uuid4()),
        status=TaskStatus.queued,
        file_name=file.filename,
        audio_duration=get_audio_duration(audio),
        language=model_params.language,
        task_type=TaskType.transcription,
        task_params={
            **model_params.model_dump(),
            "asr_options": asr_options_params.model_dump(),
            "vad_options": vad_options_params.model_dump(),
        },
    )

    identifier = await repository.add(task)

    background_tasks.add_task(
        process_transcribe,
        audio,
        identifier,
        model_params,
        asr_options_params,
        vad_options_params,
        transcription_service,
    )

    logger.info(TASK_SCHEDULED_LOG_FORMAT, identifier)
    return Response(identifier=identifier, message=TASK_QUEUED_MESSAGE)


@service_router.post(
    "/service/align",
    tags=["Speech-2-Text services"],
    name="2. Align Transcript",
)
async def align(
    background_tasks: BackgroundTasks,
    align_params: Annotated[AlignmentParams, Depends()],
    repository: TaskRepositoryDependency,
    file_service: FileServiceDependency,
    alignment_service: AlignmentServiceDependency,
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
        alignment_service (IAlignmentService): Alignment service dependency.

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
        raise FileValidationError(
            filename="unknown", reason="Transcript filename is missing"
        )

    file_service.validate_file_extension(transcript.filename, {JSON_EXTENSION})

    try:
        # Read the content of the transcript file
        transcript_data = Transcript(**json.loads(transcript.file.read()))
    except PydanticValidationError as e:
        logger.error("Invalid JSON content in transcript file: %s", str(e))
        raise ValidationError(
            message=f"Invalid JSON content in transcript file: {str(e)}",
            code="INVALID_TRANSCRIPT_JSON",
            user_message="The transcript file contains invalid JSON.",
        )

    # Validate and save audio file
    if file.filename is None:
        raise FileValidationError(
            filename="unknown", reason="Audio filename is missing"
        )

    file_service.validate_file_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = file_service.save_upload(file)
    audio = process_audio_file(temp_file)

    # Create domain task
    task = DomainTask(
        uuid=str(uuid4()),
        status=TaskStatus.queued,
        file_name=file.filename,
        audio_duration=get_audio_duration(audio),
        language=transcript_data.language,
        task_type=TaskType.transcription_alignment,
        task_params={
            **align_params.model_dump(),
            "device": device,
        },
    )

    identifier = await repository.add(task)

    background_tasks.add_task(
        process_alignment,
        audio,
        transcript_data.model_dump(),
        identifier,
        device,
        align_params,
        alignment_service,
    )

    logger.info(TASK_SCHEDULED_LOG_FORMAT, identifier)
    return Response(identifier=identifier, message=TASK_QUEUED_MESSAGE)


@service_router.post(
    "/service/diarize", tags=["Speech-2-Text services"], name="3. Diarize"
)
async def diarize(
    background_tasks: BackgroundTasks,
    repository: TaskRepositoryDependency,
    diarize_params: Annotated[DiarizationParams, Depends()],
    file_service: FileServiceDependency,
    diarization_service: DiarizationServiceDependency,
    file: UploadFile = File(...),
    device: Device = Query(
        default=Config.DEVICE,
        description="Device to use for PyTorch inference",
    ),
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
        diarization_service (IDiarizationService): Diarization service dependency.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info("Received diarization request for file: %s", file.filename)

    # Validate and save file using file service
    if file.filename is None:
        raise FileValidationError(filename="unknown", reason="Filename is missing")

    file_service.validate_file_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = file_service.save_upload(file)
    audio = process_audio_file(temp_file)

    # Create domain task
    task = DomainTask(
        uuid=str(uuid4()),
        status=TaskStatus.queued,
        file_name=file.filename,
        audio_duration=get_audio_duration(audio),
        task_type=TaskType.diarization,
        task_params={
            **diarize_params.model_dump(),
            "device": device,
        },
    )

    identifier = await repository.add(task)

    background_tasks.add_task(
        process_diarize,
        audio,
        identifier,
        device,
        diarize_params,
        diarization_service,
    )

    logger.info(TASK_SCHEDULED_LOG_FORMAT, identifier)
    return Response(identifier=identifier, message=TASK_QUEUED_MESSAGE)


@service_router.post(
    "/service/combine",
    tags=["Speech-2-Text services"],
    name="4. Combine Transcript and Diarization result",
)
async def combine(
    background_tasks: BackgroundTasks,
    repository: TaskRepositoryDependency,
    file_service: FileServiceDependency,
    speaker_service: SpeakerAssignmentServiceDependency,
    aligned_transcript: UploadFile = File(...),
    diarization_result: UploadFile = File(...),
) -> Response:
    """
    Combine a transcript with diarization results.

    Args:
        background_tasks (BackgroundTasks): Background tasks dependency.
        aligned_transcript (UploadFile): Uploaded aligned transcript file.
        diarization_result (UploadFile): Uploaded diarization result file.
        repository (ITaskRepository): Task repository dependency.
        file_service (FileService): File service dependency.
        speaker_service (ISpeakerAssignmentService): Speaker assignment service dependency.

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
        raise FileValidationError(
            filename="unknown", reason="Aligned transcript filename is missing"
        )
    if diarization_result.filename is None:
        raise FileValidationError(
            filename="unknown", reason="Diarization result filename is missing"
        )

    file_service.validate_file_extension(aligned_transcript.filename, {JSON_EXTENSION})
    file_service.validate_file_extension(diarization_result.filename, {JSON_EXTENSION})

    try:
        # Read the content of the transcript file
        transcript = AlignedTranscription(**json.loads(aligned_transcript.file.read()))
        # removing words within each segment that have missing start, end, or score values
        transcript = filter_aligned_transcription(transcript)
    except PydanticValidationError as e:
        logger.error("Invalid JSON content in aligned transcript file: %s", str(e))
        raise ValidationError(
            message=f"Invalid JSON content in aligned transcript file: {str(e)}",
            code="INVALID_TRANSCRIPT_JSON",
            user_message="The aligned transcript file contains invalid JSON.",
        )
    try:
        # Map JSON to list of models
        diarization_segments = []
        for item in json.loads(diarization_result.file.read()):
            diarization_segments.append(DiarizationSegment(**item))
    except PydanticValidationError as e:
        logger.error("Invalid JSON content in diarization result file: %s", str(e))
        raise ValidationError(
            message=f"Invalid JSON content in diarization result file: {str(e)}",
            code="INVALID_DIARIZATION_JSON",
            user_message="The diarization result file contains invalid JSON.",
        )

    # Create domain task
    task = DomainTask(
        uuid=str(uuid4()),
        status=TaskStatus.queued,
        file_name=None,
        task_type=TaskType.combine_transcript_diarization,
    )

    identifier = await repository.add(task)

    background_tasks.add_task(
        process_speaker_assignment,
        pd.json_normalize([segment.model_dump() for segment in diarization_segments]),
        transcript.model_dump(),
        identifier,
        speaker_service,
    )

    logger.info(TASK_SCHEDULED_LOG_FORMAT, identifier)
    return Response(identifier=identifier, message=TASK_QUEUED_MESSAGE)
