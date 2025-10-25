"""This module provides services for transcribing, diarizing, and aligning audio using Whisper and other models."""

import gc
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import torch
from opentelemetry import context
from whisperx import (
    align,
    load_align_model,
    load_model,
)
from whisperx.diarize import DiarizationPipeline

from app.core.config import Config
from app.core.logging import logger
from app.domain.repositories.task_repository import ITaskRepository
from app.domain.services.alignment_service import IAlignmentService
from app.domain.services.diarization_service import IDiarizationService
from app.domain.services.speaker_assignment_service import ISpeakerAssignmentService
from app.domain.services.transcription_service import ITranscriptionService
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.repositories.sqlalchemy_task_repository import (
    SQLAlchemyTaskRepository,
)
from app.schemas import (
    AlignedTranscription,
    ComputeType,
    Device,
    SpeechToTextProcessingParams,
    TaskStatus,
    WhisperModel,
)
from app.transcript import filter_aligned_transcription


def transcribe_with_whisper(
    audio: np.ndarray[Any, np.dtype[np.float32]],
    task: str,
    asr_options: dict[str, Any],
    vad_options: dict[str, Any],
    language: str,
    batch_size: int = 16,
    chunk_size: int = 20,
    model: WhisperModel = Config.WHISPER_MODEL,
    device: Device = Config.DEVICE,
    device_index: int = 0,
    compute_type: ComputeType = Config.COMPUTE_TYPE,
    threads: int = 0,
) -> dict[str, Any]:
    """
    Transcribe an audio file using the Whisper model.

    Args:
       audio (Audio): The audio to transcribe.
       batch_size (int): Batch size for transcription (default 16).
       chunk_size (int): Chunk size for transcription (default 20).
       model (WhisperModel): Name of the Whisper model to use.
       device (Device): Device to use for PyTorch inference.
       device_index (int): Device index to use for FasterWhisper inference.
       compute_type (ComputeType): Compute type for computation.

    Returns:
       Transcript: The transcription result.
    """
    logger.debug(
        "Starting transcription with Whisper model: %s on device: %s",
        model.value,
        device.value,
    )
    # Log GPU memory before loading model
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory before loading model - used: {torch.cuda.memory_allocated() / 1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
        )
    faster_whisper_threads = 4
    if (threads := threads) > 0:
        torch.set_num_threads(threads)
        faster_whisper_threads = threads

    logger.debug(
        "Loading model with config - model: %s, device: %s, compute_type: %s, threads: %d, task: %s, language: %s",
        model.value,
        device.value,
        compute_type.value,
        faster_whisper_threads,
        task,
        language,
    )
    loaded_model = load_model(
        model.value,
        device.value,
        device_index=device_index,
        compute_type=compute_type.value,
        asr_options=asr_options,
        vad_options=vad_options,
        language=language,
        task=task,
        threads=faster_whisper_threads,
    )
    logger.debug("Transcription model loaded successfully")
    result = loaded_model.transcribe(
        audio=audio, batch_size=batch_size, chunk_size=chunk_size, language=language
    )

    # Log GPU memory before cleanup
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory before cleanup: {torch.cuda.memory_allocated() / 1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
        )

    # delete model
    gc.collect()
    torch.cuda.empty_cache()
    del loaded_model

    # Log GPU memory after cleanup
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory after cleanup: {torch.cuda.memory_allocated() / 1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
        )

    logger.debug("Completed transcription")
    return result  # type: ignore[no-any-return]


def diarize(
    audio: np.ndarray[Any, np.dtype[np.float32]],
    device: Device = Config.DEVICE,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> pd.DataFrame:
    """
    Diarize an audio file using the PyAnnotate model.

    Args:
       audio (Audio): The audio to diarize.
       device (Device): Device to use for PyTorch inference.

    Returns:
       Diarizartion: The diarization result.
    """
    logger.debug("Starting diarization with device: %s", device.value)

    # Log GPU memory before loading model
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory before loading model - used: {torch.cuda.memory_allocated() / 1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
        )

    model = DiarizationPipeline(use_auth_token=Config.HF_TOKEN, device=device.value)
    result = model(audio=audio, min_speakers=min_speakers, max_speakers=max_speakers)

    # Log GPU memory before cleanup
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory before cleanup: {torch.cuda.memory_allocated() / 1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
        )

    # delete model
    gc.collect()
    torch.cuda.empty_cache()
    del model

    # Log GPU memory after cleanup
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory after cleanup: {torch.cuda.memory_allocated() / 1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
        )

    logger.debug("Completed diarization with device: %s", device.value)
    return result  # type: ignore[no-any-return]


def align_whisper_output(
    transcript: list[dict[str, Any]],
    audio: np.ndarray[Any, np.dtype[np.float32]],
    language_code: str,
    device: Device = Config.DEVICE,
    align_model: str | None = None,
    interpolate_method: str = "nearest",
    return_char_alignments: bool = False,
) -> dict[str, Any]:
    """
    Align the transcript to the original audio.

    Args:
       transcript: The text transcript.
       audio: The original audio.
       language_code: The language code.
       device (Device): Device to use for PyTorch inference.
       align_model: Name of phoneme-level ASR model to do alignment.
       interpolate_method: For word .srt, method to assign timestamps to non-aligned words, or merge them into neighboring.
       return_char_alignments: Whether to return character-level alignments in the output json file.

    Returns:
       The aligned transcript.
    """
    logger.debug(
        "Starting alignment for language code: %s on device: %s",
        language_code,
        device.value,
    )

    # Log GPU memory before loading model
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory before loading model - used: {torch.cuda.memory_allocated() / 1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
        )

    logger.debug(
        "Loading align model with config - language_code: %s, device: %s, interpolate_method: %s, return_char_alignments: %s",
        language_code,
        device.value,
        interpolate_method,
        return_char_alignments,
    )
    align_model, align_metadata = load_align_model(
        language_code=language_code, device=device.value, model_name=align_model
    )

    result = align(
        transcript,
        align_model,
        align_metadata,
        audio,
        device.value,
        interpolate_method=interpolate_method,
        return_char_alignments=return_char_alignments,
    )

    # Log GPU memory before cleanup
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory before cleanup: {torch.cuda.memory_allocated() / 1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
        )

    # delete model
    gc.collect()
    torch.cuda.empty_cache()
    del align_model
    del align_metadata

    # Log GPU memory after cleanup
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory after cleanup: {torch.cuda.memory_allocated() / 1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
        )

    logger.debug("Completed alignment")
    return result  # type: ignore[no-any-return]


def process_audio_common(
    params: SpeechToTextProcessingParams,
    trace_context: Any = None,
    transcription_service: ITranscriptionService | None = None,
    alignment_service: IAlignmentService | None = None,
    diarization_service: IDiarizationService | None = None,
    speaker_service: ISpeakerAssignmentService | None = None,
) -> None:
    """
    Process an audio clip to generate a transcript with speaker labels.

    Args:
        params (SpeechToTextProcessingParams): The speech-to-text processing parameters
        trace_context: OpenTelemetry trace context from parent span
        transcription_service: Transcription service (defaults to WhisperX if None)
        alignment_service: Alignment service (defaults to WhisperX if None)
        diarization_service: Diarization service (defaults to WhisperX if None)
        speaker_service: Speaker assignment service (defaults to WhisperX if None)

    Returns:
        None: The result is saved in the transcription requests dict.
    """
    # Import here to avoid circular dependency
    from app.infrastructure.ml import (
        WhisperXAlignmentService,
        WhisperXDiarizationService,
        WhisperXSpeakerAssignmentService,
        WhisperXTranscriptionService,
    )

    # Use provided services or create default WhisperX implementations
    transcription_svc = transcription_service or WhisperXTranscriptionService()
    alignment_svc = alignment_service or WhisperXAlignmentService()
    diarization_svc = diarization_service or WhisperXDiarizationService(
        hf_token=Config.HF_TOKEN or ""
    )
    speaker_svc = speaker_service or WhisperXSpeakerAssignmentService()

    # Attach trace context if provided (from parent request span)
    token = None
    if trace_context is not None:
        token = context.attach(trace_context)

    try:
        # Create repository for this background task
        session = SessionLocal()
        repository: ITaskRepository = SQLAlchemyTaskRepository(session)

        try:
            start_time = datetime.now()
            logger.info(
                "Starting speech-to-text processing for identifier: %s",
                params.identifier,
            )

            logger.debug(
                "Transcription parameters - task: %s, language: %s, batch_size: %d, chunk_size: %d, model: %s, device: %s, device_index: %d, compute_type: %s, threads: %d",
                params.whisper_model_params.task.value,
                params.whisper_model_params.language,
                params.whisper_model_params.batch_size,
                params.whisper_model_params.chunk_size,
                params.whisper_model_params.model.value,
                params.whisper_model_params.device.value,
                params.whisper_model_params.device_index,
                params.whisper_model_params.compute_type.value,
                params.whisper_model_params.threads,
            )

            segments_before_alignment = transcription_svc.transcribe(
                audio=params.audio,
                task=params.whisper_model_params.task.value,
                asr_options=params.asr_options.model_dump(),
                vad_options=params.vad_options.model_dump(),
                language=params.whisper_model_params.language,
                batch_size=params.whisper_model_params.batch_size,
                chunk_size=params.whisper_model_params.chunk_size,
                model=params.whisper_model_params.model.value,
                device=params.whisper_model_params.device.value,
                device_index=params.whisper_model_params.device_index,
                compute_type=params.whisper_model_params.compute_type.value,
                threads=params.whisper_model_params.threads,
            )

            logger.debug(
                "Alignment parameters - align_model: %s, interpolate_method: %s, return_char_alignments: %s, language_code: %s",
                params.alignment_params.align_model,
                params.alignment_params.interpolate_method,
                params.alignment_params.return_char_alignments,
                segments_before_alignment["language"],
            )
            segments_transcript = alignment_svc.align(
                transcript=segments_before_alignment["segments"],
                audio=params.audio,
                language_code=segments_before_alignment["language"],
                device=params.whisper_model_params.device.value,
                align_model=params.alignment_params.align_model,
                interpolate_method=params.alignment_params.interpolate_method,
                return_char_alignments=params.alignment_params.return_char_alignments,
            )
            transcript = AlignedTranscription(**segments_transcript)
            # removing words within each segment that have missing start, end, or score values
            filtered_transcript = filter_aligned_transcription(transcript)
            transcript_dict = filtered_transcript.model_dump()

            logger.debug(
                "Diarization parameters - device: %s, min_speakers: %s, max_speakers: %s",
                params.whisper_model_params.device.value,
                params.diarization_params.min_speakers,
                params.diarization_params.max_speakers,
            )
            diarization_segments = diarization_svc.diarize(
                audio=params.audio,
                device=params.whisper_model_params.device.value,
                min_speakers=params.diarization_params.min_speakers,
                max_speakers=params.diarization_params.max_speakers,
            )

            logger.debug("Starting to combine transcript with diarization results")
            result = speaker_svc.assign_speakers(diarization_segments, transcript_dict)

            logger.debug("Completed combining transcript with diarization results")

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(
                "Completed speech-to-text processing for identifier: %s. Duration: %ss",
                params.identifier,
                duration,
            )

            repository.update(
                identifier=params.identifier,
                update_data={
                    "status": TaskStatus.completed,
                    "result": result,
                    "duration": duration,
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )
        except (RuntimeError, ValueError, KeyError) as e:
            logger.error(
                "Speech-to-text processing failed for identifier: %s. Error: %s",
                params.identifier,
                str(e),
            )
            repository.update(
                identifier=params.identifier,
                update_data={
                    "status": TaskStatus.failed,
                    "error": str(e),
                },
            )
        except MemoryError as e:
            logger.error(
                f"Task failed for identifier {params.identifier} due to out of memory. Error: {str(e)}"
            )
            repository.update(
                identifier=params.identifier,
                update_data={"status": TaskStatus.failed, "error": str(e)},
            )
        finally:
            session.close()
    finally:
        # Detach trace context if it was attached
        if token is not None:
            context.detach(token)
