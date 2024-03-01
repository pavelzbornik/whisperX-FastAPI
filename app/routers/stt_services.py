from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile

from sqlalchemy.orm import Session
from ..db import get_db_session, db_session

from ..tasks import add_task_to_db

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

from ..services import (
    process_transcribe,
    process_diarize,
    process_alignment,
    process_speaker_assignment,
)

from ..transcript import filter_aligned_transcription

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
    task: str = Query(
        default="transcribe",
        description="whether to perform X->X speech recognition ('transcribe') or X->English translation ('translate')",
        enum=["transcribe", "translate"],
    ),
    file: UploadFile = File(..., description="Audio/video file to transcribe"),
    session: Session = Depends(get_db_session),
    model: WhisperModel = Query(
        default=WHISPER_MODEL, description="Name of the Whisper model to use"
    ),
    device: Device = Query(
        default=device,
        description="Device to use for PyTorch inference",
    ),
    device_index: int = Query(
        default=0,
        description="Device index to use for FasterWhisper inference",
    ),
    batch_size: int = Query(
        default=8, description="The preferred batch size for inference"
    ),
    compute_type: ComputeType = Query(
        default="float16", description="Type of computation"
    ),
    temperature: float = Query(
        0, description="temperature to use for sampling"
    ),
    beam_size: int = Query(
        default=5,
        description="number of beams in beam search, only applicable when temperature is zero",
    ),
    patience: float = Query(
        default=1.0,
        description="optional patience value to use in beam decoding",
    ),
    length_penalty: float = Query(
        default=1.0, description="optional token length penalty coefficient"
    ),
    suppress_tokens: str = Query(
        default="-1",
        description="comma-separated list of token ids to suppress during sampling",
    ),
    suppress_numerals: bool = Query(
        default=False,
        description="whether to suppress numeric symbols and currency symbols during sampling",
    ),
    initial_prompt: str = Query(
        default=None,
        description="optional text to provide as a prompt for the first window.",
    ),
    compression_ratio_threshold: float = Query(
        default=2.4,
        description="if the gzip compression ratio is higher than this value, treat the decoding as failed",
    ),
    logprob_threshold: float = Query(
        default=-1.0,
        description="if the average log probability is lower than this value, treat the decoding as failed",
    ),
    no_speech_threshold: float = Query(
        default=0.6,
        description="if the probability of the token is higher than this value AND the decoding has failed due to `logprob_threshold`, consider the segment as silence",
    ),
    vad_onset: float = Query(
        default=0.500,
        description="Onset threshold for VAD (see pyannote.audio), reduce this if speech is not being detected",
    ),
    vad_offset: float = Query(
        default=0.363,
        description="Offset threshold for VAD (see pyannote.audio), reduce this if speech is not being detected.",
    ),
    threads: int = Query(
        default=0,
        description="number of threads used by torch for CPU inference; supercedes MKL_NUM_THREADS/OMP_NUM_THREADS",
    ),
) -> Response:

    validate_extension(file.filename, ALLOWED_EXTENSIONS)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = whisperx.load_audio(temp_file)

    db_session.set(session)

    asr_options = {
        "beam_size": beam_size,
        "patience": patience,
        "length_penalty": length_penalty,
        "temperatures": temperature,
        "compression_ratio_threshold": compression_ratio_threshold,
        "log_prob_threshold": logprob_threshold,
        "no_speech_threshold": no_speech_threshold,
        "condition_on_previous_text": False,
        "initial_prompt": initial_prompt,
        "suppress_tokens": [int(x) for x in suppress_tokens.split(",")],
        "suppress_numerals": suppress_numerals,
    }
    vad_options = {"vad_onset": vad_onset, "vad_offset": vad_offset}

    identifier = add_task_to_db(
        status="processing",
        file_name=file.filename,
        language=language,
        task_type="transcription",
        task_params={
            "task": task,
            "batch_size": batch_size,
            "model": model,
            "device": device,
            "device_index": device_index,
            "compute_type": compute_type,
            "asr_options": asr_options,
            "vad_options": vad_options,
            "threads": threads,
        },
        session=session,
    )

    background_tasks.add_task(
        process_transcribe,
        audio,
        identifier,
        task,
        language,
        batch_size,
        model,
        device,
        device_index,
        compute_type,
        asr_options,
        vad_options,
        threads,
        # session,
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
    align_model: str = Query(
        None, description="Name of phoneme-level ASR model to do alignment"
    ),
    interpolate_method: str = Query(
        "nearest",
        description="For word .srt, method to assign timestamps to non-aligned words, or merge them into neighboring.",
        enum=["nearest", "linear", "ignore"],
    ),
    return_char_alignments: bool = Query(
        False,
        description="Return character-level alignments in the output json file",
    ),
    session: Session = Depends(get_db_session),
):
    validate_extension(transcript.filename, {".json"})

    db_session.set(session)

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
        status="processing",
        file_name=file.filename,
        language=transcript.language,
        task_type="transcription_aligment",
        task_params={
            "align_model": align_model,
            "interpolate_method": interpolate_method,
            "device": device,
            "return_char_alignments": return_char_alignments,
        },
        session=session,
    )

    background_tasks.add_task(
        process_alignment,
        audio,
        transcript.model_dump(),
        identifier,
        device,
        align_model,
        interpolate_method,
        return_char_alignments,
        # session,
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
    min_speakers: int = Query(
        None, description="Minimum number of speakers to in audio file"
    ),
    max_speakers: int = Query(
        None, description="Maximum number of speakers to in audio file"
    ),
) -> Response:

    validate_extension(file.filename, ALLOWED_EXTENSIONS)

    db_session.set(session)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = whisperx.load_audio(temp_file)

    identifier = add_task_to_db(
        # identifier=identifier,
        status="processing",
        file_name=file.filename,
        task_type="diarization",
        task_params={
            "min_speakers": min_speakers,
            "max_speakers": max_speakers,
            "device": device,
        },
        session=session,
    )
    background_tasks.add_task(
        process_diarize,
        audio,
        identifier,
        device,
        min_speakers,
        max_speakers,
        # session,
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
        # session,
    )

    return Response(identifier=identifier, message="Task queued")
