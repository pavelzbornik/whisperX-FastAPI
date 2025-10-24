"""Domain service interfaces for ML operations."""

from app.domain.services.transcription_service import ITranscriptionService
from app.domain.services.diarization_service import IDiarizationService
from app.domain.services.alignment_service import IAlignmentService
from app.domain.services.speaker_assignment_service import ISpeakerAssignmentService

__all__ = [
    "ITranscriptionService",
    "IDiarizationService",
    "IAlignmentService",
    "ISpeakerAssignmentService",
]
