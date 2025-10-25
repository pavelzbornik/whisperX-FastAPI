"""Audio processing task handler for background execution."""

import logging
from typing import Any

from app.domain.services.alignment_service import IAlignmentService
from app.domain.services.diarization_service import IDiarizationService
from app.domain.services.speaker_assignment_service import ISpeakerAssignmentService
from app.domain.services.transcription_service import ITranscriptionService

logger = logging.getLogger(__name__)


def create_audio_processing_handler(
    transcription_service: ITranscriptionService,
    diarization_service: IDiarizationService,
    alignment_service: IAlignmentService,
    speaker_service: ISpeakerAssignmentService,
) -> dict[str, Any]:
    """
    Create audio processing handlers with injected dependencies.

    This factory function creates a set of audio processing handlers
    (transcription, diarization, alignment, speaker assignment) with
    their ML service dependencies injected.

    The handlers are stateless and can be safely registered in the
    task registry for background execution.

    Args:
        transcription_service: WhisperX transcription service
        diarization_service: WhisperX diarization service
        alignment_service: WhisperX alignment service
        speaker_service: Speaker assignment service

    Returns:
        Dictionary mapping task types to handler functions

    Example:
        >>> handlers = create_audio_processing_handler(
        ...     transcription_service,
        ...     diarization_service,
        ...     alignment_service,
        ...     speaker_service
        ... )
        >>> registry.register("transcription", handlers["transcription"])
    """

    def transcription_handler(
        audio: Any,
        task: str,
        asr_options: dict[str, Any],
        vad_options: dict[str, Any],
        language: str,
        batch_size: int,
        chunk_size: int,
        model: str,
        device: str,
        device_index: int,
        compute_type: str,
        threads: int,
    ) -> dict[str, Any]:
        """
        Handle transcription task.

        Args:
            audio: Audio data
            task: Transcription task type
            asr_options: ASR options
            vad_options: VAD options
            language: Language code
            batch_size: Batch size for processing
            chunk_size: Chunk size for processing
            model: Model name
            device: Device (cpu/cuda)
            device_index: Device index
            compute_type: Compute type
            threads: Number of threads

        Returns:
            Transcription result
        """
        logger.info(f"Processing transcription task with model {model}")
        return transcription_service.transcribe(
            audio=audio,
            task=task,
            asr_options=asr_options,
            vad_options=vad_options,
            language=language,
            batch_size=batch_size,
            chunk_size=chunk_size,
            model=model,
            device=device,
            device_index=device_index,
            compute_type=compute_type,
            threads=threads,
        )

    def diarization_handler(
        audio: Any,
        device: str,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Handle diarization task.

        Args:
            audio: Audio data
            device: Device (cpu/cuda)
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers

        Returns:
            Diarization result as list of dictionaries
        """
        logger.info(f"Processing diarization task on {device}")
        result = diarization_service.diarize(
            audio=audio,
            device=device,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
        # Convert DataFrame to dict for JSON serialization
        return result.drop(columns=["segment"]).to_dict(orient="records")  # type: ignore[return-value]

    def alignment_handler(
        audio: Any,
        segments: list[dict[str, Any]],
        language_code: str,
        device: str,
        align_model: str | None = None,
        interpolate_method: str = "nearest",
        return_char_alignments: bool = False,
    ) -> dict[str, Any]:
        """
        Handle alignment task.

        Args:
            audio: Audio data
            segments: Transcript segments
            language_code: Language code
            device: Device (cpu/cuda)
            align_model: Alignment model name
            interpolate_method: Interpolation method
            return_char_alignments: Whether to return character alignments

        Returns:
            Alignment result
        """
        logger.info(f"Processing alignment task for language {language_code}")
        return alignment_service.align(
            transcript=segments,
            audio=audio,
            language_code=language_code,
            device=device,
            align_model=align_model,
            interpolate_method=interpolate_method,
            return_char_alignments=return_char_alignments,
        )

    def speaker_assignment_handler(
        diarization_segments: Any,
        transcript: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle speaker assignment task.

        Args:
            diarization_segments: Diarization segments
            transcript: Transcript data

        Returns:
            Combined transcript with speaker labels
        """
        logger.info("Processing speaker assignment task")
        return speaker_service.assign_speakers(
            diarization_segments=diarization_segments,
            transcript=transcript,
        )

    return {
        "transcription": transcription_handler,
        "diarization": diarization_handler,
        "transcription_alignment": alignment_handler,
        "combine_transcript&diarization": speaker_assignment_handler,
    }
