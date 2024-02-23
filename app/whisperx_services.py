import whisperx

from fastapi import Depends
from datetime import datetime
import torch
import os

from sqlalchemy.orm import Session


from .tasks import (
    update_task_status_in_db,
)

from .db import get_db_session

import gc

LANG = "en"
HF_TOKEN = os.getenv("HF_TOKEN")
WHISPER_MODEL = os.getenv("WHISPER_MODEL")

device = "cuda" if torch.cuda.is_available() else "cpu"


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
