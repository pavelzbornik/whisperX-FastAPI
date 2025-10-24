"""Dependency injection providers for FastAPI endpoints."""

from collections.abc import Generator

from fastapi import Depends

from app.core.config import Config
from app.domain.repositories.task_repository import ITaskRepository
from app.domain.services.transcription_service import ITranscriptionService
from app.domain.services.diarization_service import IDiarizationService
from app.domain.services.alignment_service import IAlignmentService
from app.domain.services.speaker_assignment_service import ISpeakerAssignmentService
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.repositories.sqlalchemy_task_repository import (
    SQLAlchemyTaskRepository,
)
from app.infrastructure.ml import (
    WhisperXTranscriptionService,
    WhisperXDiarizationService,
    WhisperXAlignmentService,
    WhisperXSpeakerAssignmentService,
)
from app.services.file_service import FileService
from app.services.task_management_service import TaskManagementService


def get_task_repository() -> Generator[ITaskRepository, None, None]:
    """
    Provide a task repository implementation for dependency injection.

    This function creates a new database session and repository instance
    for each request. The session is automatically closed when the request
    is complete.

    Background tasks create their own sessions directly using SessionLocal()
    and SQLAlchemyTaskRepository() rather than using dependency injection.

    Yields:
        ITaskRepository: A task repository implementation

    Example:
        >>> @router.post("/tasks")
        >>> async def create_task(
        ...     repository: ITaskRepository = Depends(get_task_repository)
        ... ):
        ...     task_id = repository.add(task)
        ...     return {"id": task_id}
    """
    session = SessionLocal()
    try:
        yield SQLAlchemyTaskRepository(session)
    finally:
        session.close()


def get_file_service() -> FileService:
    """
    Provide a FileService instance for dependency injection.

    FileService is stateless, so we return a new instance for each request.

    Returns:
        FileService: A file service instance
    """
    return FileService()


def get_task_management_service(
    repository: ITaskRepository = Depends(get_task_repository),
) -> Generator[TaskManagementService, None, None]:
    """
    Provide a TaskManagementService instance for dependency injection.

    The service is initialized with a task repository.

    Args:
        repository: Task repository from get_task_repository

    Yields:
        TaskManagementService: A task management service instance
    """
    yield TaskManagementService(repository)


def get_transcription_service() -> ITranscriptionService:
    """
    Provide a transcription service implementation for dependency injection.

    Returns WhisperX implementation by default. Can be overridden for testing
    by using app.dependency_overrides.

    Returns:
        ITranscriptionService: A transcription service implementation

    Example:
        >>> @router.post("/transcribe")
        >>> async def transcribe(
        ...     transcription: ITranscriptionService = Depends(get_transcription_service)
        ... ):
        ...     result = transcription.transcribe(audio, params)
        ...     return result
    """
    return WhisperXTranscriptionService()


def get_diarization_service() -> IDiarizationService:
    """
    Provide a diarization service implementation for dependency injection.

    Returns WhisperX/PyAnnote implementation by default. Can be overridden
    for testing by using app.dependency_overrides.

    Returns:
        IDiarizationService: A diarization service implementation

    Example:
        >>> @router.post("/diarize")
        >>> async def diarize(
        ...     diarization: IDiarizationService = Depends(get_diarization_service)
        ... ):
        ...     result = diarization.diarize(audio, device)
        ...     return result
    """
    hf_token = Config.HF_TOKEN or ""
    return WhisperXDiarizationService(hf_token=hf_token)


def get_alignment_service() -> IAlignmentService:
    """
    Provide an alignment service implementation for dependency injection.

    Returns WhisperX implementation by default. Can be overridden for testing
    by using app.dependency_overrides.

    Returns:
        IAlignmentService: An alignment service implementation

    Example:
        >>> @router.post("/align")
        >>> async def align(
        ...     alignment: IAlignmentService = Depends(get_alignment_service)
        ... ):
        ...     result = alignment.align(transcript, audio, language)
        ...     return result
    """
    return WhisperXAlignmentService()


def get_speaker_assignment_service() -> ISpeakerAssignmentService:
    """
    Provide a speaker assignment service implementation for dependency injection.

    Returns WhisperX implementation by default. Can be overridden for testing
    by using app.dependency_overrides.

    Returns:
        ISpeakerAssignmentService: A speaker assignment service implementation

    Example:
        >>> @router.post("/assign-speakers")
        >>> async def assign_speakers(
        ...     speaker_service: ISpeakerAssignmentService = Depends(get_speaker_assignment_service)
        ... ):
        ...     result = speaker_service.assign_speakers(diarization, transcript)
        ...     return result
    """
    return WhisperXSpeakerAssignmentService()
