import whisperx
import requests
from tempfile import NamedTemporaryFile

import logging
from fastapi import HTTPException, Depends
from datetime import datetime
import os

from urllib.parse import urlparse

from sqlalchemy.orm import Session

from .schemas import Response
from .audio import process_audio_file
from .tasks import (
    update_task_status_in_db,
    add_task_to_db,
)

from .files import validate_extension, ALLOWED_EXTENSIONS

from .db import get_db_session

from .whisperx_services import (
    transcribe_with_whisper,
    align_whisper_output,
    diarize,
    LANG,
    process_audio_common,
)


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


def download_and_process_file(
    url,
    background_tasks,
    session,
    language=None,
):
    """
    Download an audio file from a URL and process it in the background.

    Args:
        audio_url (str): The URL of the audio file to download.
        background_tasks (BackgroundTasks): The BackgroundTasks object.

    Returns:
        None: The result is saved in the transcription requests dict.
    """
    filename = os.path.basename(urlparse(url).path)

    _, original_extension = os.path.splitext(filename)

    # Create a temporary file with the original extension

    temp_audio_file = NamedTemporaryFile(
        suffix=original_extension, delete=False
    )
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=8192):
            temp_audio_file.write(chunk)

    validate_extension(temp_audio_file.name, ALLOWED_EXTENSIONS)
    if language:
        validate_language_code(language)

    identifier = add_task_to_db(
        status="processing",
        file_name=temp_audio_file.name,
        task_type="full_process",
        session=session,
    )
    audio = process_audio_file(temp_audio_file.name)
    # Use background tasks to perform the audio processing
    background_tasks.add_task(
        process_audio_common,
        audio,
        identifier,
        session,
        language,
    )

    # Return the identifier to the user
    return Response(identifier=identifier, message="Task queued")


def process_audio_task(
    audio_processor,
    identifier: str,
    task_type: str,
    session: Session = Depends(get_db_session),
    *args,
):
    try:
        start_time = datetime.now()

        result = audio_processor(*args)

        if task_type == "diarization":
            result = result.drop(columns=["segment"]).to_dict(orient="records")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        update_task_status_in_db(
            identifier=identifier,
            update_data={
                "status": "completed",
                "result": result,
                "duration": duration,
            },
            session=session,
        )

    except Exception as e:
        logging.error(
            f"Task {task_type} failed for identifier {identifier}. Error: {str(e)}"
        )
        update_task_status_in_db(
            identifier=identifier,
            update_data={
                "status": "failed",
                "error": str(e),
            },
            session=session,
        )


def process_transcribe(
    audio,
    identifier,
    language=LANG,
    session: Session = Depends(get_db_session),
):
    process_audio_task(
        transcribe_with_whisper,
        identifier,
        "transcription",
        session,
        audio,
        language,
    )


def process_diarize(
    audio, identifier, session: Session = Depends(get_db_session)
):
    process_audio_task(
        diarize,
        identifier,
        "diarization",
        session,
        audio,
    )


def process_alignment(
    audio,
    transcript,
    identifier,
    session: Session = Depends(get_db_session),
):
    process_audio_task(
        align_whisper_output,
        identifier,
        "transcription_alignment",
        session,
        transcript["segments"],
        audio,
        transcript["language"],
    )


def process_speaker_assignment(
    diarization_segments,
    transcript,
    identifier,
    session: Session = Depends(get_db_session),
):
    process_audio_task(
        whisperx.assign_word_speakers,
        identifier,
        "combine_transcript&diarization",
        session,
        diarization_segments,
        transcript,
    )
