"""This module provides services for processing audio tasks including transcription, diarization, alignment, and speaker assignment using WhisperX and FastAPI."""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from whisperx import utils as whisperx_utils

from app.core.exceptions import (
    AudioProcessingError,
    DiarizationFailedError,
    InsufficientMemoryError,
    TranscriptionFailedError,
    ValidationError,
)
from app.core.logging import logger
from app.domain.services.alignment_service import IAlignmentService
from app.domain.services.diarization_service import IDiarizationService
from app.domain.services.speaker_assignment_service import ISpeakerAssignmentService
from app.domain.services.transcription_service import ITranscriptionService
from app.infrastructure.database.connection import SyncSessionLocal
from app.infrastructure.database.repositories.sqlalchemy_task_repository import (
    SyncSQLAlchemyTaskRepository,
)
from app.schemas import (
    AlignmentParams,
    ASROptions,
    Device,
    DiarizationParams,
    TaskStatus,
    VADOptions,
    WhisperModelParams,
)


def _identify_and_store_speakers(
    diarization_result: Any,
    identifier: str,
    session: Any,
    identify: bool = False,
    auto_store: bool = False,
    threshold: float = 0.7,
) -> Any:
    """
    Identify speakers against the local DB and optionally store new ones.

    Args:
        diarization_result: The diarization result with embeddings
        identifier: The task identifier (used as task_uuid for stored speakers)
        session: The sync DB session
        identify: Whether to identify speakers against the DB
        auto_store: Whether to auto-store unidentified speakers
        threshold: Cosine similarity threshold for identification

    Returns:
        Updated DiarizationResult with known speaker labels
    """
    from uuid import uuid4

    import numpy as np

    from app.domain.entities.speaker_embedding import SpeakerEmbedding
    from app.infrastructure.database.repositories.sqlalchemy_speaker_embedding_repository import (
        SyncSQLAlchemySpeakerEmbeddingRepository,
    )

    if not diarization_result.speaker_embeddings:
        return diarization_result

    speaker_repo = SyncSQLAlchemySpeakerEmbeddingRepository(session)
    known_speakers = speaker_repo.get_all()

    label_map: dict[str, str] = {}
    new_speakers: list[SpeakerEmbedding] = []

    for speaker_label, embedding in diarization_result.speaker_embeddings.items():
        query = np.array(embedding, dtype=np.float64)
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            continue

        best_match: tuple[SpeakerEmbedding, float] | None = None
        for known in known_speakers:
            vec = np.array(known.embedding, dtype=np.float64)
            vec_norm = np.linalg.norm(vec)
            if vec_norm == 0:
                continue
            similarity = float(np.dot(query, vec) / (query_norm * vec_norm))
            if similarity >= threshold and (
                best_match is None or similarity > best_match[1]
            ):
                best_match = (known, similarity)

        if best_match is not None:
            label_map[speaker_label] = best_match[0].speaker_label
            logger.info(
                "Task %s: identified %s as %s (similarity: %.3f)",
                identifier,
                speaker_label,
                best_match[0].speaker_label,
                best_match[1],
            )
        elif auto_store:
            new_speaker = SpeakerEmbedding(
                uuid=str(uuid4()),
                speaker_label=speaker_label,
                embedding=embedding,
                task_uuid=identifier,
            )
            new_speakers.append(new_speaker)
            logger.info(
                "Task %s: auto-stored new speaker %s", identifier, speaker_label
            )

    if new_speakers:
        speaker_repo.add_batch(new_speakers)

    # Remap labels in segments DataFrame
    if label_map:
        diarization_result.segments["speaker"] = diarization_result.segments[
            "speaker"
        ].replace(label_map)
        # Also update the embeddings dict keys
        updated_embeddings = {}
        for old_label, emb in diarization_result.speaker_embeddings.items():
            new_label = label_map.get(old_label, old_label)
            updated_embeddings[new_label] = emb
        diarization_result.speaker_embeddings = updated_embeddings

    return diarization_result


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
    use_gpu_semaphore: bool = False,
    identify_speakers: bool = False,
    auto_store_speakers: bool = False,
) -> None:
    """
    Process an audio task.

    Args:
        audio_processor: Parameterless callable that returns the processing result.
        identifier (str): The task identifier.
        task_type (str): The type of the task.
        use_gpu_semaphore: Whether to acquire the GPU semaphore before processing.
        identify_speakers: Whether to match speakers against local DB.
        auto_store_speakers: Whether to auto-store unidentified speakers.
    """
    from app.core.gpu_semaphore import get_gpu_semaphore

    # Create repository for this background task (sync — runs in thread pool)
    session = SyncSessionLocal()
    repository: SyncSQLAlchemyTaskRepository = SyncSQLAlchemyTaskRepository(session)

    try:
        gpu_semaphore = get_gpu_semaphore() if use_gpu_semaphore else None

        if gpu_semaphore is not None:
            logger.info("Task %s waiting for GPU slot", identifier)
            gpu_semaphore.acquire()

        try:
            # Transition queued → processing and record start time
            start_time = datetime.now(tz=timezone.utc)
            repository.update(
                identifier=identifier,
                update_data={
                    "status": TaskStatus.processing,
                    "start_time": start_time,
                },
            )
            logger.info("Starting %s task for identifier %s", task_type, identifier)

            result = audio_processor()

            if task_type == "diarization":
                from app.domain.entities.diarization_result import DiarizationResult

                if isinstance(result, DiarizationResult):
                    if identify_speakers or auto_store_speakers:
                        result = _identify_and_store_speakers(
                            diarization_result=result,
                            identifier=identifier,
                            session=session,
                            identify=identify_speakers,
                            auto_store=auto_store_speakers,
                        )
                    result = result.to_serializable()
                else:
                    result = result.drop(columns=["segment"]).to_dict(orient="records")

            end_time = datetime.now(tz=timezone.utc)
            duration = (end_time - start_time).total_seconds()
            logger.info(
                "Completed %s task for identifier %s. Duration: %ss",
                task_type,
                identifier,
                duration,
            )

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
            logger.error(
                "Task %s failed for identifier %s. Error: %s",
                task_type,
                identifier,
                str(e),
            )
            repository.update(
                identifier=identifier,
                update_data={"status": TaskStatus.failed, "error": str(e)},
            )
        except Exception as e:
            logger.error(
                "Task %s failed for identifier %s with unexpected error. Error: %s",
                task_type,
                identifier,
                str(e),
            )
            repository.update(
                identifier=identifier,
                update_data={"status": TaskStatus.failed, "error": str(e)},
            )
        finally:
            if gpu_semaphore is not None:
                gpu_semaphore.release()
                logger.info("GPU slot released for task %s", identifier)

    finally:
        session.close()


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
        use_gpu_semaphore=model_params.device == Device.cuda,
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
            return_embeddings=diarize_params.return_embeddings
            or diarize_params.identify_speakers,
        )

    process_audio_task(
        diarize_task,
        identifier,
        "diarization",
        use_gpu_semaphore=device == Device.cuda,
        identify_speakers=diarize_params.identify_speakers,
        auto_store_speakers=diarize_params.auto_store_speakers,
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
        use_gpu_semaphore=device == Device.cuda,
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
