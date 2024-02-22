import whisperx
import requests
from tempfile import NamedTemporaryFile

import logging
from fastapi import HTTPException, Depends
from datetime import datetime
import torch
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from .models import Response
from .audio import process_audio_file
from .tasks import (
    update_task_status_in_db,
    add_task_to_db,
)

from .files import validate_extension, ALLOWED_EXTENSIONS

from .db import get_db_session

import gc

# Load environment variables from .env
load_dotenv()

LANG = "en"
HF_TOKEN = os.getenv("HF_TOKEN")
WHISPER_MODEL = os.getenv("WHISPER_MODEL")


device = "cuda" if torch.cuda.is_available() else "cpu"


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


def transcribe_with_whisper(
    audio,
    language=LANG,
    batch_size: int = 16,
):
    """
    Transcribe an audio file using the Whisper model.

    Args:
       audio (Audio): The audio to transcribe.
       batch_size (int): Batch size for transcription (default 16).

    Returns:
       Transcript: The transcription result.
    """
    model = whisperx.load_model(WHISPER_MODEL, device)
    result = model.transcribe(
        audio=audio, batch_size=batch_size, language=language
    )

    # delete model
    gc.collect()
    torch.cuda.empty_cache()
    del model

    return result


def diarize(audio):
    """
    Diarize an audio file using the PyAnnotate model.

    Args:
       audio (Audio): The audio to diarize.

    Returns:
       Diarizartion: The diarization result.
    """
    model = whisperx.DiarizationPipeline(
        use_auth_token=HF_TOKEN, device=device
    )
    result = model(audio)

    # delete model
    gc.collect()
    torch.cuda.empty_cache()
    del model

    return result


def align_whisper_output(transcript, audio, language_code):
    """
    Align the transcript to the original audio.

    Args:
       Transcript: The text transcript.
       audio (Audio): The original audio.
       language_code (str): The language code.

    Returns:
       Transcript: The aligned transcript.
    """

    align_model, align_metadata = whisperx.load_align_model(
        language_code=language_code, device=device
    )

    result = whisperx.align(
        transcript,
        align_model,
        align_metadata,
        audio,
        device,
        return_char_alignments=False,
    )

    # delete model
    gc.collect()
    torch.cuda.empty_cache()
    del align_model
    del align_metadata

    return result


def process_audio_common(
    audio,
    identifier,
    session: Session = Depends(get_db_session),
    language=LANG,
):
    """
    Process an audio clip to generate a transcript with speaker labels.

    Args:
        audio (Audio): The input audio
        identifier (str): The identifier for the request

    Returns:
        None: The result is saved in the transcription requests dict.
    """
    try:
        start_time = datetime.now()
        segments_before_alignment = transcribe_with_whisper(
            audio, language=language
        )
        segments_transcript = align_whisper_output(
            transcript=segments_before_alignment["segments"],
            audio=audio,
            language_code=segments_before_alignment["language"],
        )

        diarization_segments = diarize(audio)

        result = whisperx.assign_word_speakers(
            diarization_segments, segments_transcript
        )

        for segment in result["segments"]:
            del segment["words"]

        del result["word_segments"]

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
        update_task_status_in_db(
            identifier=identifier,
            update_data={
                "status": "failed",
                "error": str(e),
            },
            session=session,
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
