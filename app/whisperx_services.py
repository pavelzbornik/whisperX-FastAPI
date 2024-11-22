import gc
import os
from datetime import datetime

import torch
from whisperx import (
    DiarizationPipeline,
    align,
    assign_word_speakers,
    load_align_model,
    load_model,
)

from .schemas import AlignedTranscription, SpeechToTextProcessingParams
from .tasks import update_task_status_in_db
from .transcript import filter_aligned_transcription

LANG = os.getenv("DEFAULT_LANG", "en")
HF_TOKEN = os.getenv("HF_TOKEN")
WHISPER_MODEL = os.getenv("WHISPER_MODEL")

device = "cuda" if torch.cuda.is_available() else "cpu"
compute_type = "float16" if torch.cuda.is_available() else "int8"


def transcribe_with_whisper(
    audio,
    task,
    asr_options,
    vad_options,
    language,
    batch_size: int = 16,
    model: str = WHISPER_MODEL,
    device: str = device,
    device_index: int = 0,
    compute_type: str = compute_type,
    threads: int = 0,
):
    """
    Transcribe an audio file using the Whisper model.

    Args:
       audio (Audio): The audio to transcribe.
       batch_size (int): Batch size for transcription (default 16).
       model (str): Name of the Whisper model to use.
       device (str): Device to use for PyTorch inference.
       device_index (int): Device index to use for FasterWhisper inference.
       compute_type (str): Compute type for computation.

    Returns:
       Transcript: The transcription result.
    """
    faster_whisper_threads = 4
    if (threads := threads) > 0:
        torch.set_num_threads(threads)
        faster_whisper_threads = threads

    model = load_model(
        model,
        device,
        device_index=device_index,
        compute_type=compute_type,
        asr_options=asr_options,
        vad_options=vad_options,
        language=language,
        task=task,
        threads=faster_whisper_threads,
    )
    result = model.transcribe(audio=audio, batch_size=batch_size, language=language)

    # delete model
    gc.collect()
    torch.cuda.empty_cache()
    del model

    return result


def diarize(audio, device, min_speakers=None, max_speakers=None):
    """
    Diarize an audio file using the PyAnnotate model.

    Args:
       audio (Audio): The audio to diarize.

    Returns:
       Diarizartion: The diarization result.
    """
    model = DiarizationPipeline(use_auth_token=HF_TOKEN, device=device)
    result = model(audio=audio, min_speakers=min_speakers, max_speakers=max_speakers)

    # delete model
    gc.collect()
    torch.cuda.empty_cache()
    del model

    return result


def align_whisper_output(
    transcript,
    audio,
    language_code,
    device: str = device,
    align_model: str = None,
    interpolate_method: str = "nearest",
    return_char_alignments: bool = False,
):
    """
    Align the transcript to the original audio.

    Args:
       transcript: The text transcript.
       audio: The original audio.
       language_code: The language code.
       align_model: Name of phoneme-level ASR model to do alignment.
       interpolate_method: For word .srt, method to assign timestamps to non-aligned words, or merge them into neighboring.
       return_char_alignments: Whether to return character-level alignments in the output json file.

    Returns:
       The aligned transcript.
    """

    align_model, align_metadata = load_align_model(
        language_code=language_code, device=device, model_name=align_model
    )

    result = align(
        transcript,
        align_model,
        align_metadata,
        audio,
        device,
        interpolate_method=interpolate_method,
        return_char_alignments=return_char_alignments,
    )

    # delete model
    gc.collect()
    torch.cuda.empty_cache()
    del align_model
    del align_metadata

    return result


def process_audio_common(params: SpeechToTextProcessingParams, session):
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

        print(params.whisper_model_params.task.value)
        segments_before_alignment = transcribe_with_whisper(
            audio=params.audio,
            task=params.whisper_model_params.task,
            asr_options=params.asr_options,
            vad_options=params.vad_options,
            language=params.whisper_model_params.language,
            batch_size=params.whisper_model_params.batch_size,
            model=params.whisper_model_params.model,
            device=params.whisper_model_params.device,
            device_index=params.whisper_model_params.device_index,
            compute_type=params.whisper_model_params.compute_type,
            threads=params.whisper_model_params.threads,
        )

        segments_transcript = align_whisper_output(
            transcript=segments_before_alignment["segments"],
            audio=params.audio,
            language_code=segments_before_alignment["language"],
            align_model=params.alignment_params.align_model,
            interpolate_method=params.alignment_params.interpolate_method,
            return_char_alignments=params.alignment_params.return_char_alignments,
        )
        transcript = AlignedTranscription(**segments_transcript)
        # removing words within each segment that have missing start, end, or score values
        transcript = filter_aligned_transcription(transcript).model_dump()

        diarization_segments = diarize(
            params.audio,
            device=params.whisper_model_params.device,
            min_speakers=params.diarization_params.min_speakers,
            max_speakers=params.diarization_params.max_speakers,
        )

        result = assign_word_speakers(diarization_segments, transcript)

        for segment in result["segments"]:
            del segment["words"]

        del result["word_segments"]

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        update_task_status_in_db(
            identifier=params.identifier,
            update_data={
                "status": "completed",
                "result": result,
                "duration": duration,
            },
            session=session,
        )
    except Exception as e:
        update_task_status_in_db(
            identifier=params.identifier,
            update_data={
                "status": "failed",
                "error": str(e),
            },
            session=session,
        )
