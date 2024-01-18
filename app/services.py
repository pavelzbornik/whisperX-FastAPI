import whisperx
import requests
from tempfile import NamedTemporaryFile

import logging
from fastapi import HTTPException
from datetime import datetime
import torch
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

from .models import Response
from .audio import process_audio_file
from .tasks import generate_unique_identifier, update_transcription_status

from .files import validate_extension, ALLOWED_EXTENSIONS

# Load environment variables from .env
load_dotenv()

LANG = "en"
HF_TOKEN = os.getenv("HF_TOKEN")
WHISPER_MODEL = os.getenv("WHISPER_MODEL")


# Load models during startup
device = "cuda" if torch.cuda.is_available() else "cpu"
transcription_model = whisperx.load_model(WHISPER_MODEL, device)
diarize_model = whisperx.DiarizationPipeline(
    use_auth_token=HF_TOKEN, device=device
)
align_model, align_metadata = whisperx.load_align_model(
    language_code=LANG, device=device
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


def transcribe_with_whisper(
    audio,
    model,
    language=LANG,
    batch_size: int = 16,
):
    """
    Transcribe an audio file using the Whisper model.

    Args:
       audio (Audio): The audio to transcribe.
       model (Model): The Whisper model to use.
       batch_size (int): Batch size for transcription (default 16).

    Returns:
       Transcript: The transcription result.
    """

    return model.transcribe(
        audio=audio, batch_size=batch_size, language=language
    )


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
    # Use the global align_model and align_metadata
    global align_model, align_metadata
    # if the language code is different from the default language
    if language_code != LANG:
        align_model, align_metadata = whisperx.load_align_model(
            language_code=language_code, device=device
        )

    return whisperx.align(
        transcript,
        align_model,
        align_metadata,
        audio,
        device,
        return_char_alignments=False,
    )


async def process_audio_common(audio, identifier, language=LANG):
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
            audio, model=transcription_model, language=language
        )
        segments_transcript = align_whisper_output(
            transcript=segments_before_alignment["segments"],
            audio=audio,
            language_code=segments_before_alignment["language"],
        )

        diarization_segments = diarize_model(audio)

        result = whisperx.assign_word_speakers(
            diarization_segments, segments_transcript
        )

        for segment in result["segments"]:
            del segment["words"]

        del result["word_segments"]

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        update_transcription_status(
            identifier=identifier,
            status="completed",
            result=result,
            task_type="full_process",
            duration=duration,
        )
    except Exception as e:
        update_transcription_status(
            identifier=identifier,
            status="failed",
            result=None,
            task_type="full_process",
            duration=None,
            error=str(e),
        )


def download_and_process_file(url, background_tasks, language=None):
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

    # Generate a unique identifier for the transcription request
    identifier = generate_unique_identifier()

    validate_extension(temp_audio_file.name, ALLOWED_EXTENSIONS)
    if language:
        validate_language_code(language)

    # Save the identifier and set the initial status to "processing"
    update_transcription_status(
        identifier=identifier,
        status="processing",
        file_name=temp_audio_file.name,
        task_type="full_process",
    )
    audio = process_audio_file(temp_audio_file.name)
    # Use background tasks to perform the audio processing
    background_tasks.add_task(
        process_audio_common, audio, identifier, language
    )

    # Return the identifier to the user
    return Response(identifier=identifier, message="Task queued")


def process_audio_task(audio_processor, identifier, task_type, *args):
    try:
        start_time = datetime.now()

        result = audio_processor(*args)

        if task_type == "diarization":
            result = result.drop(columns=["segment"]).to_dict(orient="records")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        update_transcription_status(
            identifier,
            "completed",
            result,
            task_type=task_type,
            duration=duration,
        )

    except Exception as e:
        logging.error(
            f"Task {task_type} failed for identifier {identifier}. Error: {str(e)}"
        )
        update_transcription_status(
            identifier,
            "failed",
            result=None,
            task_type=task_type,
            duration=None,
            error=str(e),
        )


def process_transcribe(audio, identifier, language=LANG):
    process_audio_task(
        transcribe_with_whisper,
        identifier,
        "transcription",
        audio,
        transcription_model,
        language,
    )


def process_diarize(audio, identifier):
    process_audio_task(diarize_model, identifier, "diarization", audio)


def process_alignment(audio, transcript, identifier):
    process_audio_task(
        align_whisper_output,
        identifier,
        "transcription_alignment",
        transcript["segments"],
        audio,
        transcript["language"],
    )


def process_speaker_assignment(diarization_segments, transcript, identifier):
    process_audio_task(
        whisperx.assign_word_speakers,
        identifier,
        "combine_transcript&diarization",
        diarization_segments,
        transcript,
    )


# def process_transcribe(audio, identifier):
#     """
#     Process an audio file to generate a transcript.

#     Args:
#         audio (Audio): The input audio
#         identifier (str): The identifier for the request

#     Returns:
#         None: The result is saved in the transcription requests dict.

#     """
#     try:
#         start_time = datetime.now()
#         result = transcribe_with_whisper(audio, model=transcription_model)
#         end_time = datetime.now()
#         duration = (end_time - start_time).total_seconds()

#         update_transcription_status(
#             identifier,
#             "completed",
#             result,
#             task_type="transcription",
#             duration=duration,
#         )
#     except Exception as e:
#         update_transcription_status(
#             identifier,
#             "failed",
#             result=None,
#             task_type="transcription",
#             duration=None,
#             error=str(e),
#         )


# def process_diarize(audio, identifier):
#     """
#     Process an audio file to generate speaker diarization.

#     Args:
#         audio (Audio): The input audio
#         identifier (str): The request identifier

#     Returns:
#         None: Result saved in requests dict
#     """

#     try:
#         start_time = datetime.now()

#         diarization_segments = diarize_model(audio)

#         result = diarization_segments.drop(columns=["segment"]).to_dict(
#             orient="records"
#         )
#         print(result)

#         end_time = datetime.now()
#         duration = (end_time - start_time).total_seconds()

#         update_transcription_status(
#             identifier,
#             "completed",
#             result,
#             task_type="diarization",
#             duration=duration,
#         )

#     except Exception as e:
#         update_transcription_status(
#             identifier,
#             "failed",
#             result=None,
#             task_type="diarization",
#             duration=None,
#             error=str(e),
#         )


# def process_alignment(audio, transcript, identifier):
#     try:
#         start_time = datetime.now()

#         result = align_whisper_output(
#             transcript=transcript["segments"],
#             audio=audio,
#             language_code=transcript["language"],
#         )
#         # print(result)
#         end_time = datetime.now()
#         duration = (end_time - start_time).total_seconds()

#         update_transcription_status(
#             identifier,
#             "completed",
#             result,
#             task_type="transcription_aligment",
#             duration=duration,
#         )

#     except Exception as e:
#         update_transcription_status(
#             identifier,
#             "failed",
#             result=None,
#             task_type="transcription_aligment",
#             duration=None,
#             error=str(e),
#         )


# def process_speaker_assignment(diarization_segments, transcript, identifier):
#     try:
#         start_time = datetime.now()

#         result = whisperx.assign_word_speakers(
#             diarization_segments, transcript
#         )

#         for segment in result["segments"]:
#             del segment["words"]

#         del result["word_segments"]

#         end_time = datetime.now()
#         duration = (end_time - start_time).total_seconds()

#         update_transcription_status(
#             identifier,
#             "completed",
#             result,
#             task_type="combine_transcript&diarization",
#             duration=duration,
#         )

#     except Exception as e:
#         update_transcription_status(
#             identifier,
#             "failed",
#             result=None,
#             task_type="combine_transcript&diarization",
#             duration=None,
#             error=str(e),
#         )
