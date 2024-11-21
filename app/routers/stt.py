import logging
from fastapi import (
    File,
    UploadFile,
    Form,
    Depends,
    APIRouter,
)
from fastapi import BackgroundTasks

import os
from urllib.parse import urlparse

from ..schemas import (
    Response,
    ASROptions,
    VADOptions,
    WhsiperModelParams,
    AlignmentParams,
    DiarizationParams,
    SpeechToTextProcessingParams,
)

from sqlalchemy.orm import Session

from ..audio import (
    process_audio_file,
    get_audio_duration,
)

from ..files import (
    save_temporary_file,
    validate_extension,
    ALLOWED_EXTENSIONS,
)

from ..tasks import (
    add_task_to_db,
)

from ..whisperx_services import process_audio_common

import requests
from tempfile import NamedTemporaryFile

from ..db import get_db_session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

stt_router = APIRouter()

@stt_router.post("/speech-to-text", tags=["Speech-2-Text"])
async def speech_to_text(
    background_tasks: BackgroundTasks,
    model_params: WhsiperModelParams = Depends(),
    align_params: AlignmentParams = Depends(),
    diarize_params: DiarizationParams = Depends(),
    asr_options_params: ASROptions = Depends(),
    vad_options_params: VADOptions = Depends(),
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
) -> Response:
    logger.info("Received file upload request: %s", file.filename)

    validate_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = save_temporary_file(file.file, file.filename)
    logger.info("Temporary file saved: %s", temp_file)

    audio = process_audio_file(temp_file)
    logger.info("Audio file processed: duration %s seconds", get_audio_duration(audio))

    identifier = add_task_to_db(
        status="processing",
        file_name=file.filename,
        audio_duration=get_audio_duration(audio),
        language=model_params.language,
        task_type="full_process",
        task_params={
            **model_params.model_dump(),
            **align_params.model_dump(),
            "asr_options": asr_options_params.model_dump(),
            "vad_options": vad_options_params.model_dump(),
            **diarize_params.model_dump(),
        },
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
    model_params: WhsiperModelParams = Depends(),
    align_params: AlignmentParams = Depends(),
    diarize_params: DiarizationParams = Depends(),
    asr_options_params: ASROptions = Depends(),
    vad_options_params: VADOptions = Depends(),
    url: str = Form(...),
    session: Session = Depends(get_db_session),
) -> Response:
    logger.info("Received URL for processing: %s", url)

    # Extract filename from HTTP response headers or URL
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        
        # Check for filename in Content-Disposition header
        content_disposition = response.headers.get('Content-Disposition')
        if content_disposition and 'filename=' in content_disposition:
            filename = content_disposition.split('filename=')[1].strip('"')
        else:
            # Fall back to extracting from the URL path
            filename = os.path.basename(url)
        
        # Get the file extension
        _, original_extension = os.path.splitext(filename)

        # Save the file to a temporary location
        temp_audio_file = NamedTemporaryFile(suffix=original_extension, delete=False)
        for chunk in response.iter_content(chunk_size=8192):
            temp_audio_file.write(chunk)

    logger.info("File downloaded and saved temporarily: %s", temp_audio_file.name)
    validate_extension(temp_audio_file.name, ALLOWED_EXTENSIONS)

    audio = process_audio_file(temp_audio_file.name)
    logger.info("Audio file processed: duration %s seconds", get_audio_duration(audio))

    identifier = add_task_to_db(
        status="processing",
        file_name=temp_audio_file.name,
        audio_duration=get_audio_duration(audio),
        language=model_params.language,
        task_type="full_process",
        task_params={
            **model_params.model_dump(),
            **align_params.model_dump(),
            "asr_options": asr_options_params.model_dump(),
            "vad_options": vad_options_params.model_dump(),
            **diarize_params.model_dump(),
        },
        url=url,
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
