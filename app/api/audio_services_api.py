"""
This module provides API endpoints for speech-to-text services including transcription.

Alignment, diarization, and combining transcripts with diarization results.
"""

import json
from uuid import uuid4

import pandas as pd
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Query,
    Request,
    UploadFile,
)
from pydantic import ValidationError as PydanticValidationError
from starlette.responses import Response as StarletteResponse

from app.api.constants import (
    JSON_EXTENSION,
    TASK_QUEUED_MESSAGE,
    TASK_SCHEDULED_LOG_FORMAT,
)
from app.api.dependencies import (
    get_alignment_service,
    get_diarization_service,
    get_file_service,
    get_speaker_assignment_service,
    get_task_repository,
    get_transcription_service,
)
from app.audio import get_audio_duration, process_audio_file
from app.core.config import Config
from app.core.exceptions import FileValidationError, ValidationError
from app.core.logging import logger
from app.core.rate_limit import limiter, rate_limit_value, rate_limiting_disabled
from app.domain.entities.task import Task as DomainTask
from app.domain.repositories.task_repository import ITaskRepository
from app.domain.services.alignment_service import IAlignmentService
from app.domain.services.diarization_service import IDiarizationService
from app.domain.services.speaker_assignment_service import ISpeakerAssignmentService
from app.domain.services.transcription_service import ITranscriptionService
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


def _parse_transcript_payload(payload: bytes) -> Transcript:
    """Parse an uploaded transcript JSON payload.

    Accepts either the bare ``Transcript`` shape (``{segments, language}``)
    or the wrapped envelope returned by ``GET /task/{identifier}``
    (``{status, result, metadata, error}``) — in the latter case the inner
    ``result`` is unwrapped before validation.
    """
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error("Transcript file is not valid JSON: %s", str(e))
        raise ValidationError(
            message=f"Transcript file is not valid JSON: {e!s}",
            code="INVALID_TRANSCRIPT_JSON",
            user_message="The transcript file contains invalid JSON.",
        ) from e

    # Auto-unwrap the GET /task/{id} envelope when the user uploads it as-is.
    if (
        isinstance(data, dict)
        and "segments" not in data
        and isinstance(data.get("result"), dict)
    ):
        data = data["result"]

    try:
        return Transcript(**data)
    except (PydanticValidationError, TypeError) as e:
        logger.error("Invalid JSON content in transcript file: %s", str(e))
        raise ValidationError(
            message=f"Invalid JSON content in transcript file: {e!s}",
            code="INVALID_TRANSCRIPT_JSON",
            user_message="The transcript file contains invalid JSON.",
        ) from e


@service_router.post(
    "/service/transcribe",
    tags=["Speech-2-Text services"],
    name="1. Transcribe",
)
@limiter.limit(rate_limit_value, exempt_when=rate_limiting_disabled)
async def transcribe(
    request: Request,
    response: StarletteResponse,
    background_tasks: BackgroundTasks,
    model_params: WhisperModelParams = Depends(),
    asr_options_params: ASROptions = Depends(),
    vad_options_params: VADOptions = Depends(),
    file: UploadFile = File(..., description="Audio/video file to transcribe"),
    repository: ITaskRepository = Depends(get_task_repository),
    file_service: FileService = Depends(get_file_service),
    transcription_service: ITranscriptionService = Depends(get_transcription_service),
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
@limiter.limit(rate_limit_value, exempt_when=rate_limiting_disabled)
async def align(
    request: Request,
    response: StarletteResponse,
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
    alignment_service: IAlignmentService = Depends(get_alignment_service),
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

    transcript_data = _parse_transcript_payload(await transcript.read())

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
@limiter.limit(rate_limit_value, exempt_when=rate_limiting_disabled)
async def diarize(
    request: Request,
    response: StarletteResponse,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    repository: ITaskRepository = Depends(get_task_repository),
    device: Device = Query(
        default=Config.DEVICE,
        description="Device to use for PyTorch inference",
    ),
    diarize_params: DiarizationParams = Depends(),
    file_service: FileService = Depends(get_file_service),
    diarization_service: IDiarizationService = Depends(get_diarization_service),
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
@limiter.limit(rate_limit_value, exempt_when=rate_limiting_disabled)
async def combine(
    request: Request,
    response: StarletteResponse,
    background_tasks: BackgroundTasks,
    aligned_transcript: UploadFile = File(...),
    diarization_result: UploadFile = File(...),
    repository: ITaskRepository = Depends(get_task_repository),
    file_service: FileService = Depends(get_file_service),
    speaker_service: ISpeakerAssignmentService = Depends(
        get_speaker_assignment_service
    ),
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
