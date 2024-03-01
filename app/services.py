import whisperx

import logging
from fastapi import HTTPException
from datetime import datetime

from .tasks import (
    update_task_status_in_db,
)
from .schemas import (
    AlignmentParams,
    WhsiperModelParams,
    ASROptions,
    VADOptions,
    DiarizationParams,
)

from .db import db_session, get_db_session

from fastapi import Depends
from sqlalchemy.orm import Session

from .whisperx_services import (
    transcribe_with_whisper,
    align_whisper_output,
    diarize,
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


def process_audio_task(
    audio_processor,
    identifier: str,
    task_type: str,
    *args,
):
    session: Session = db_session.get(default=None)
    print("Session:", session)
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
    model_params: WhsiperModelParams,
    asr_options_params: ASROptions,
    vad_options_params: VADOptions,
    # session: Session = Depends(get_db_session),
):
    process_audio_task(
        transcribe_with_whisper,
        identifier,
        "transcription",
        # session,
        audio,
        model_params.task,
        asr_options_params.model_dump(),
        vad_options_params.model_dump(),
        model_params.language,
        model_params.batch_size,
        model_params.model,
        model_params.device,
        model_params.device_index,
        model_params.compute_type,
        model_params.threads,
    )


def process_diarize(
    audio,
    identifier,
    device,
    diarize_params: DiarizationParams,
    # session: Session = Depends(get_db_session),
):
    process_audio_task(
        diarize,
        identifier,
        "diarization",
        audio,
        device,
        diarize_params.min_speakers,
        diarize_params.max_speakers,
    )


def process_alignment(
    audio,
    transcript,
    identifier,
    device,
    align_params: AlignmentParams,
):
    process_audio_task(
        align_whisper_output,
        identifier,
        "transcription_alignment",
        transcript["segments"],
        audio,
        transcript["language"],
        device,
        align_params.align_model,
        align_params.interpolate_method,
        align_params.return_char_alignments,
    )


def process_speaker_assignment(
    diarization_segments,
    transcript,
    identifier,
    # session: Session = Depends(get_db_session),
):
    process_audio_task(
        whisperx.assign_word_speakers,
        identifier,
        "combine_transcript&diarization",
        # session,
        diarization_segments,
        transcript,
    )
