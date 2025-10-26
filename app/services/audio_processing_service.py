"""This module provides services for processing audio tasks including transcription, diarization, alignment, and speaker assignment using WhisperX and FastAPI."""

import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from opentelemetry import context
from opentelemetry.trace import Status, StatusCode
from whisperx import utils as whisperx_utils

from app.core.exceptions import (
    AudioProcessingError,
    DiarizationFailedError,
    InsufficientMemoryError,
    TranscriptionFailedError,
    ValidationError,
)
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
from app.observability.metrics import get_metrics
from app.observability.tracing import get_tracer
from app.schemas import (
    AlignmentParams,
    ASROptions,
    Device,
    DiarizationParams,
    TaskStatus,
    VADOptions,
    WhisperModelParams,
)

# Get tracer and metrics
tracer = get_tracer(__name__)
metrics = get_metrics()


def validate_language_code(language_code: str) -> None:
    """
    Validate the language code.

    Args:
        language_code (str): The language code to validate.

    Raises:
        ValidationError: If the language code is invalid.
    """
    if language_code not in whisperx_utils.LANGUAGES:
        raise ValidationError(
            message=f"Invalid language code: {language_code}",
            code="INVALID_LANGUAGE_CODE",
            user_message=f"Language code '{language_code}' is not supported.",
            language_code=language_code,
        )


def process_audio_task(
    audio_processor: Callable[[], Any],
    identifier: str,
    task_type: str,
    trace_context: context.Context | None = None,
) -> None:
    """
    Process an audio task with OpenTelemetry tracing and metrics.

    Args:
        audio_processor: Parameterless callable that returns the processing result.
        identifier (str): The task identifier.
        task_type (str): The type of the task.
        trace_context: Optional trace context from parent span.
    """
    # Attach trace context if provided (from background task)
    token = None
    if trace_context is not None:
        token = context.attach(trace_context)

    # Create repository for this background task
    session = SessionLocal()
    repository: ITaskRepository = SQLAlchemyTaskRepository(session)

    # Increment active tasks
    metrics.active_tasks.add(1, {"status": "processing", "task_type": task_type})

    # Create span for the entire task
    with tracer.start_as_current_span(
        f"audio_processing.{task_type}",
        attributes={
            "task.id": identifier,
            "task.type": task_type,
        },
    ) as span:
        try:
            start_time = datetime.now()
            processing_start = time.time()
            logger.info(f"Starting {task_type} task for identifier {identifier}")

            span.add_event("task_started", {"task_id": identifier})

            result = audio_processor()

            if task_type == "diarization":
                result = result.drop(columns=["segment"]).to_dict(orient="records")

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(
                f"Completed {task_type} task for identifier {identifier}. Duration: {duration}s"
            )

            # Record span attributes
            span.set_attributes(
                {
                    "task.duration_seconds": duration,
                    "task.status": "completed",
                }
            )
            span.add_event("task_completed", {"duration_seconds": duration})

            repository.update(
                identifier=identifier,
                update_data={
                    "status": TaskStatus.completed,
                    "result": result,
                    "duration": duration,
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )

            # Record success metrics
            metrics.audio_processing_requests_total.add(
                1, {"status": "success", "task_type": task_type}
            )
            metrics.audio_processing_duration_seconds.record(
                time.time() - processing_start, {"task_type": task_type}
            )

            # Set span status to OK
            span.set_status(Status(StatusCode.OK))

        except (
            ValueError,
            TypeError,
            RuntimeError,
            MemoryError,
            TranscriptionFailedError,
            DiarizationFailedError,
            AudioProcessingError,
            InsufficientMemoryError,
        ) as e:
            error_type = type(e).__name__
            logger.error(
                f"Task {task_type} failed for identifier {identifier}. Error: {str(e)}"
            )

            # Record exception in span
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.set_attribute("task.status", "failed")
            span.set_attribute("error.type", error_type)

            repository.update(
                identifier=identifier,
                update_data={"status": TaskStatus.failed, "error": str(e)},
            )

            # Record failure metrics
            metrics.audio_processing_requests_total.add(
                1,
                {"status": "error", "task_type": task_type, "error_type": error_type},
            )

        except Exception as e:
            error_type = type(e).__name__
            logger.error(
                f"Task {task_type} failed for identifier {identifier} with unexpected error. Error: {str(e)}"
            )

            # Record exception in span
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.set_attribute("task.status", "failed")
            span.set_attribute("error.type", error_type)

            repository.update(
                identifier=identifier,
                update_data={"status": TaskStatus.failed, "error": str(e)},
            )

            # Record failure metrics
            metrics.audio_processing_requests_total.add(
                1,
                {"status": "error", "task_type": task_type, "error_type": error_type},
            )

        finally:
            # Decrement active tasks
            metrics.active_tasks.add(
                -1, {"status": "processing", "task_type": task_type}
            )

            session.close()

            # Detach trace context if it was attached
            if token is not None:
                context.detach(token)


def process_transcribe(
    audio: Any,
    identifier: str,
    model_params: WhisperModelParams,
    asr_options_params: ASROptions,
    vad_options_params: VADOptions,
    transcription_service: ITranscriptionService,
) -> None:
    """
    Process a transcription task using the transcription service.

    Args:
        audio: The audio data.
        identifier (str): The task identifier.
        model_params (WhisperModelParams): The model parameters.
        asr_options_params (ASROptions): The ASR options.
        vad_options_params (VADOptions): The VAD options.
        transcription_service: The transcription service to use.
    """

    def transcribe_task() -> Any:
        return transcription_service.transcribe(
            audio=audio,
            task=model_params.task.value,
            asr_options=asr_options_params.model_dump(),
            vad_options=vad_options_params.model_dump(),
            language=model_params.language,
            batch_size=model_params.batch_size,
            chunk_size=model_params.chunk_size,
            model=model_params.model.value,
            device=model_params.device.value,
            device_index=model_params.device_index,
            compute_type=model_params.compute_type.value,
            threads=model_params.threads,
        )

    process_audio_task(
        transcribe_task,
        identifier,
        "transcription",
    )


def process_diarize(
    audio: Any,
    identifier: str,
    device: Device,
    diarize_params: DiarizationParams,
    diarization_service: IDiarizationService,
) -> None:
    """
    Process a diarization task using the diarization service.

    Args:
        audio: The audio data.
        identifier (str): The task identifier.
        device (Device): The device to use.
        diarize_params (DiarizationParams): The diarization parameters.
        diarization_service: The diarization service to use.
    """

    def diarize_task() -> Any:
        return diarization_service.diarize(
            audio=audio,
            device=device.value,
            min_speakers=diarize_params.min_speakers,
            max_speakers=diarize_params.max_speakers,
        )

    process_audio_task(
        diarize_task,
        identifier,
        "diarization",
    )


def process_alignment(
    audio: Any,
    transcript: dict[str, Any],
    identifier: str,
    device: Device,
    align_params: AlignmentParams,
    alignment_service: IAlignmentService,
) -> None:
    """
    Process a transcription alignment task using the alignment service.

    Args:
        audio: The audio data.
        transcript: The transcript data.
        identifier (str): The task identifier.
        device (Device): The device to use.
        align_params (AlignmentParams): The alignment parameters.
        alignment_service: The alignment service to use.
    """

    def align_task() -> Any:
        return alignment_service.align(
            transcript=transcript["segments"],
            audio=audio,
            language_code=transcript["language"],
            device=device.value,
            align_model=align_params.align_model,
            interpolate_method=align_params.interpolate_method,
            return_char_alignments=align_params.return_char_alignments,
        )

    process_audio_task(
        align_task,
        identifier,
        "transcription_alignment",
    )


def process_speaker_assignment(
    diarization_segments: Any,
    transcript: dict[str, Any],
    identifier: str,
    speaker_service: ISpeakerAssignmentService,
) -> None:
    """
    Process a speaker assignment task using the speaker assignment service.

    Args:
        diarization_segments: The diarization segments.
        transcript: The transcript data.
        identifier (str): The task identifier.
        speaker_service: The speaker assignment service to use.
    """

    def assign_task() -> Any:
        return speaker_service.assign_speakers(
            diarization_segments=diarization_segments,
            transcript=transcript,
        )

    process_audio_task(
        assign_task,
        identifier,
        "combine_transcript&diarization",
    )
