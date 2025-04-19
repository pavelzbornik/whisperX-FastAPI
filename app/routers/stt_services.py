"""
This module provides API endpoints for speech-to-text services including transcription.

Alignment, diarization, and combining transcripts with diarization results.
"""

import json
from datetime import datetime

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
from sqlalchemy.orm import Session

from ..audio import get_audio_duration, process_audio_file
from ..db import get_db_session
from ..files import ALLOWED_EXTENSIONS, save_temporary_file, validate_extension
from ..logger import logger  # Import the logger from the new module
from ..schemas import (
    AlignedTranscription,
    AlignmentParams,
    ASROptions,
    Device,
    DiarizationParams,
    DiarizationSegment,
    Response,
    Transcript,
    VADOptions,
    WhisperModelParams,
)
from ..services import (
    process_alignment,
    process_diarize,
    process_speaker_assignment,
    process_transcribe,
)
from ..tasks import add_task_to_db
from ..transcript import filter_aligned_transcription
from ..whisperx_services import device

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
    session: Session = Depends(get_db_session),
) -> Response:
    """
    Transcribe an uploaded audio file.

    Args:
        background_tasks (BackgroundTasks): Background tasks dependency.
        model_params (WhisperModelParams): Whisper model parameters.
        asr_options_params (ASROptions): ASR options parameters.
        vad_options_params (VADOptions): VAD options parameters.
        file (UploadFile): Uploaded audio file.
        session (Session): Database session dependency.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info("Received transcription request for file: %s", file.filename)

    validate_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = process_audio_file(temp_file)

    identifier = add_task_to_db(
        status="processing",
        file_name=file.filename,
        audio_duration=get_audio_duration(audio),
        language=model_params.language,
        task_type="transcription",
        task_params={
            **model_params.model_dump(),
            "asr_options": asr_options_params.model_dump(),
            "vad_options": vad_options_params.model_dump(),
        },
        start_time=datetime.utcnow(),
        session=session,
    )

    background_tasks.add_task(
        process_transcribe,
        audio,
        identifier,
        model_params,
        asr_options_params,
        vad_options_params,
        session,
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
        default=device,
        description="Device to use for PyTorch inference",
    ),
    align_params: AlignmentParams = Depends(),
    session: Session = Depends(get_db_session),
) -> Response:
    """
    Align a transcript with an audio file.

    Args:
        background_tasks (BackgroundTasks): Background tasks dependency.
        transcript (UploadFile): Uploaded transcript file.
        file (UploadFile): Uploaded audio file.
        device (Device): Device for PyTorch inference.
        align_params (AlignmentParams): Alignment parameters.
        session (Session): Database session dependency.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info(
        "Received alignment request for file: %s and transcript: %s",
        file.filename,
        transcript.filename,
    )

    validate_extension(transcript.filename, {".json"})

    try:
        # Read the content of the transcript file
        transcript = Transcript(**json.loads(transcript.file.read()))
    except ValidationError as e:
        logger.error("Invalid JSON content in transcript file: %s", str(e))
        raise HTTPException(status_code=400, detail=f"Invalid JSON content. {str(e)}")

    validate_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = process_audio_file(temp_file)

    identifier = add_task_to_db(
        status="processing",
        file_name=file.filename,
        audio_duration=get_audio_duration(audio),
        language=transcript.language,
        task_type="transcription_alignment",
        task_params={
            **align_params.model_dump(),
            "device": device,
        },
        start_time=datetime.utcnow(),
        session=session,
    )

    background_tasks.add_task(
        process_alignment,
        audio,
        transcript.model_dump(),
        identifier,
        device,
        align_params,
        session,
    )

    logger.info("Background task scheduled for processing: ID %s", identifier)
    return Response(identifier=identifier, message="Task queued")


@service_router.post(
    "/service/diarize", tags=["Speech-2-Text services"], name="3. Diarize"
)
async def diarize(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
    device: Device = Query(
        default=device,
        description="Device to use for PyTorch inference",
    ),
    diarize_params: DiarizationParams = Depends(),
) -> Response:
    """
    Perform diarization on an uploaded audio file.

    Args:
        background_tasks (BackgroundTasks): Background tasks dependency.
        file (UploadFile): Uploaded audio file.
        session (Session): Database session dependency.
        device (Device): Device for PyTorch inference.
        diarize_params (DiarizationParams): Diarization parameters.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info("Received diarization request for file: %s", file.filename)

    validate_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = process_audio_file(temp_file)

    identifier = add_task_to_db(
        # identifier=identifier,
        status="processing",
        file_name=file.filename,
        audio_duration=get_audio_duration(audio),
        task_type="diarization",
        task_params={
            **diarize_params.model_dump(),
            "device": device,
        },
        start_time=datetime.utcnow(),
        session=session,
    )
    background_tasks.add_task(
        process_diarize,
        audio,
        identifier,
        device,
        diarize_params,
        session,
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
    session: Session = Depends(get_db_session),
) -> Response:
    """
    Combine a transcript with diarization results.

    Args:
        background_tasks (BackgroundTasks): Background tasks dependency.
        aligned_transcript (UploadFile): Uploaded aligned transcript file.
        diarization_result (UploadFile): Uploaded diarization result file.
        session (Session): Database session dependency.

    Returns:
        Response: Confirmation message of task queuing.
    """
    logger.info(
        "Received combine request for aligned transcript: %s and diarization result: %s",
        aligned_transcript.filename,
        diarization_result.filename,
    )

    validate_extension(aligned_transcript.filename, {".json"})
    validate_extension(diarization_result.filename, {".json"})

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

    identifier = add_task_to_db(
        status="processing",
        file_name=None,
        task_type="combine_transcript&diarization",
        start_time=datetime.utcnow(),
        session=session,
    )
    background_tasks.add_task(
        process_speaker_assignment,
        pd.json_normalize([segment.model_dump() for segment in diarization_segments]),
        transcript.model_dump(),
        identifier,
        session,
    )

    logger.info("Background task scheduled for processing: ID %s", identifier)
    return Response(identifier=identifier, message="Task queued")
