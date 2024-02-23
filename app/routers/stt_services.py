from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..db import get_db_session

from ..tasks import add_task_to_db

from fastapi import (
    File,
    UploadFile,
    HTTPException,
    Depends,
)
from fastapi import BackgroundTasks
import whisperx

from ..schemas import (
    Response,
    Transcript,
    AlignedTranscription,
    DiarizationSegment,
    ComputeType,
    WhisperModel,
    Device,
    
)

from pydantic import ValidationError

import pandas as pd

import json

from sqlalchemy.orm import Session

from ..services import (
    process_transcribe,
    process_diarize,
    process_alignment,
    process_speaker_assignment,
    validate_language_code,
)

from ..files import (
    save_temporary_file,
    validate_extension,
    ALLOWED_EXTENSIONS,
)

from ..whisperx_services import WHISPER_MODEL, device, LANG

service_router = APIRouter()


@service_router.post(
    "/service/transcribe",
    tags=["Speech-2-Text services"],
    name="1. Transcribe",
)
async def transcribe(
    background_tasks: BackgroundTasks,
    language: str = Query(
        default=LANG,
        description="Language to transcribe",
        enum=list(whisperx.utils.LANGUAGES.keys()),
    ),
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
    model: WhisperModel = Query(
        default=WHISPER_MODEL, description="Model to use for transcription"
    ),
    device: Device = Query(
        default=device, description="Device to run the model",
    ),
    device_index: int = 0,
    batch_size: int = 8,
    compute_type: ComputeType = Query(
        default="float16", description="Type of computation"
    ),
) -> Response:

    validate_extension(file.filename, ALLOWED_EXTENSIONS)
    if language:
        validate_language_code(language)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = whisperx.load_audio(temp_file)

    identifier = add_task_to_db(
        # identifier=identifier,
        status="processing",
        file_name=file.filename,
        language=language,
        task_type="transcription",
        task_params={
            'batch_size': batch_size,
            'model': model,
            'device': device,
            'device_index': device_index,
            'compute_type': compute_type
        },
        session=session,
    )

    background_tasks.add_task(
        process_transcribe,
        audio,
        identifier,
        language,
        session,
        batch_size,
        model,
        device,
        device_index,
        compute_type,
    )

    return Response(identifier=identifier, message="Task queued")


@service_router.post(
    "/service/align",
    tags=["Speech-2-Text services"],
    name="2. Align Transcript",
)
def align(
    background_tasks: BackgroundTasks,
    transcript: UploadFile = File(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
):
    validate_extension(transcript.filename, {".json"})

    try:
        # Read the content of the transcript file
        transcript = Transcript(**json.loads(transcript.file.read()))
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON content. {str(e)}"
        )

    validate_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = whisperx.load_audio(temp_file)

    identifier = add_task_to_db(
        # identifier=identifier,
        status="processing",
        file_name=file.filename,
        task_type="transcription_aligment",
        session=session,
    )

    background_tasks.add_task(
        process_alignment,
        audio,
        transcript.model_dump(),
        identifier,
        session,
    )

    return Response(identifier=identifier, message="Task queued")


@service_router.post(
    "/service/diarize", tags=["Speech-2-Text services"], name="3. Diarize"
)
async def diarize(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
) -> Response:

    validate_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = whisperx.load_audio(temp_file)

    identifier = add_task_to_db(
        # identifier=identifier,
        status="processing",
        file_name=file.filename,
        task_type="diarization",
        session=session,
    )
    background_tasks.add_task(process_diarize, audio, identifier, session)

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
):

    validate_extension(aligned_transcript.filename, {".json"})
    validate_extension(diarization_result.filename, {".json"})

    try:
        # Read the content of the transcript file
        transcript = AlignedTranscription(
            **json.loads(aligned_transcript.file.read())
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON content. {str(e)}"
        )
    try:
        # Map JSON to list of models
        diarization_segments = []
        for item in json.loads(diarization_result.file.read()):
            diarization_segments.append(DiarizationSegment(**item))
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON content. {str(e)}"
        )

    identifier = add_task_to_db(
        status="processing",
        file_name=None,
        task_type="combine_transcript&diarization",
        session=session,
    )
    background_tasks.add_task(
        process_speaker_assignment,
        pd.json_normalize(
            [segment.model_dump() for segment in diarization_segments]
        ),
        transcript.model_dump(),
        identifier,
        session,
    )

    return Response(identifier=identifier, message="Task queued")
