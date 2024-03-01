from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile

from sqlalchemy.orm import Session
from ..db import get_db_session, db_session

from ..tasks import add_task_to_db

from fastapi import BackgroundTasks

from ..schemas import (
    Response,
    Transcript,
    AlignedTranscription,
    DiarizationSegment,
    Device,
    AlignmentParams,
    WhsiperModelParams,
    DiarizationParams,
    ASROptions,
    VADOptions
)

from pydantic import ValidationError

import pandas as pd

import json

from ..services import (
    process_transcribe,
    process_diarize,
    process_alignment,
    process_speaker_assignment,
)

from ..audio import (
    process_audio_file,
    get_audio_duration,
)

from ..transcript import filter_aligned_transcription

from ..files import (
    save_temporary_file,
    validate_extension,
    ALLOWED_EXTENSIONS,
)

from ..whisperx_services import device

service_router = APIRouter()


@service_router.post(
    "/service/transcribe",
    tags=["Speech-2-Text services"],
    name="1. Transcribe",
)
async def transcribe(
    background_tasks: BackgroundTasks,
    model_params: WhsiperModelParams = Depends(),
    asr_options_params: ASROptions = Depends(),
    vad_options_params: VADOptions = Depends(),
    file: UploadFile = File(..., description="Audio/video file to transcribe"),
    session: Session = Depends(get_db_session),

) -> Response:

    validate_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = process_audio_file(temp_file)
    db_session.set(session)

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

    db_session.set(session)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = process_audio_file(temp_file)

    identifier = add_task_to_db(
        status="processing",
        file_name=file.filename,
        audio_duration=get_audio_duration(audio),
        language=transcript.language,
        task_type="transcription_aligment",
        task_params={
            **align_params.model_dump(),
            "device": device,
        },
        session=session,
    )

    background_tasks.add_task(
        process_alignment,
        audio,
        transcript.model_dump(),
        identifier,
        device,
        align_params,
        session
    )

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

    validate_extension(file.filename, ALLOWED_EXTENSIONS)

    db_session.set(session)

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

    db_session.set(session)

    try:
        # Read the content of the transcript file
        transcript = AlignedTranscription(
            **json.loads(aligned_transcript.file.read())
        )
        # removing words within each segment that have missing start, end, or score values
        transcript = filter_aligned_transcription(transcript)
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
