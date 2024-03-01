from fastapi import (
    File,
    UploadFile,
    Form,
    Depends,
    APIRouter,
    Query,
)
from fastapi import BackgroundTasks

from ..schemas import (
    Response,
    ComputeType,
    WhisperModel,
    Device,
    ASROptions,
    VADOptions,
    WhsiperModelParams,
    AlignmentParams,
    DiarizationParams,
    SpeechToTextProcessingParams,
)

from sqlalchemy.orm import Session

from ..services import (
    process_audio_common,
    download_and_process_file,
    process_audio_file,
    # validate_language_code,
)

from ..files import (
    save_temporary_file,
    validate_extension,
    ALLOWED_EXTENSIONS,
)

from ..tasks import (
    add_task_to_db,
)

from ..db import get_db_session, db_session

from ..whisperx_services import WHISPER_MODEL, device, LANG

from whisperx import utils


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
    """
    Process an audio/video file in the background in full process.

    Args:
        audio_file (UploadFile): The audio file to process.

    Returns:
        dict: A dictionary containing the identifier and a message. The message is "Task queued". The identifier is a unique identifier for the transcription request.
    """

    validate_extension(file.filename, ALLOWED_EXTENSIONS)
    # if model_params.language:
    #     validate_language_code(model_params.language.value)

    temp_file = save_temporary_file(file.file, file.filename)
    audio = process_audio_file(temp_file)

    # asr_options = asr_options_params.model_dump()
    # vad_options = vad_options_params.model_dump()

    db_session.set(session)

    identifier = add_task_to_db(
        status="processing",
        file_name=file.filename,
        language=model_params.language.value,
        task_type="full_process",
        task_params={
            "task": model_params.task,
            "batch_size": model_params.batch_size,
            "model": model_params.model,
            "device": model_params.device,
            "device_index": model_params.device_index,
            "compute_type": model_params.compute_type,
            "align_model": align_params.align_model,
            "interpolate_method": align_params.interpolate_method,
            "return_char_alignments": align_params.return_char_alignments,
            "asr_options": asr_options_params.model_dump(),
            "vad_options": vad_options_params.model_dump(),
            "threads": model_params.threads,
            "min_speakers": diarize_params.min_speakers,
            "max_speakers": diarize_params.max_speakers,
        },
        session=session,
    )
    # Create an instance of AudioProcessingParams
    audio_params = SpeechToTextProcessingParams(
        audio=audio,
        identifier=identifier,
        vad_options=vad_options_params,
        asr_options=asr_options_params,
        whisper_model_params=model_params,
        alignment_params=align_params,
        diarization_params=diarize_params,
    )

    # Call add_task with the process_audio_common function and the audio_params object
    background_tasks.add_task(process_audio_common, audio_params)
    # background_tasks.add_task(
    #     process_audio_common,
    #     audio,
    #     identifier,
    #     model_params.task,
    #     asr_options,
    #     vad_options,
    #     model_params.language.value,
    #     model_params.batch_size,
    #     model_params.model,
    #     model_params.device,
    #     model_params.device_index,
    #     model_params.compute_type,
    #     model_params.threads,
    #     align_params.align_model,
    #     align_params.interpolate_method,
    #     align_params.return_char_alignments,
    #     diarize_params.min_speakers,
    #     diarize_params.max_speakers,
    # )

    return Response(identifier=identifier, message="Task queued")


@stt_router.post("/speech-to-text-url", tags=["Speech-2-Text"])
async def speech_to_text_url(
    background_tasks: BackgroundTasks,
    language: str = Query(
        default=LANG,
        description="Language to transcribe",
        enum=list(utils.LANGUAGES.keys()),
    ),
    url: str = Form(...),
    task: str = Query(
        default="transcribe",
        description="whether to perform X->X speech recognition ('transcribe') or X->English translation ('translate')",
        enum=["transcribe", "translate"],
    ),
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
    min_speakers: int = Query(
        None, description="Minimum number of speakers to in audio file"
    ),
    max_speakers: int = Query(
        None, description="Maximum number of speakers to in audio file"
    ),
) -> Response:

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
    db_session.set(session)

    return download_and_process_file(
        url,
        background_tasks,
        # session,
        task,
        asr_options,
        vad_options,
        language,
        batch_size,
        model,
        device,
        device_index,
        compute_type,
        align_model,
        interpolate_method,
        return_char_alignments,
        threads,
        min_speakers,
        max_speakers,
    )
