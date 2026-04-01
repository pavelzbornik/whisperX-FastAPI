"""Dependency injection providers for FastAPI endpoints."""

from collections.abc import AsyncGenerator, Generator
from typing import Annotated

from fastapi import Depends

from app.api.constants import CONTAINER_NOT_INITIALIZED_ERROR
from app.core.container import Container
from app.domain.repositories.task_repository import ITaskRepository
from app.domain.services.alignment_service import IAlignmentService
from app.domain.services.diarization_service import IDiarizationService
from app.domain.services.speaker_assignment_service import ISpeakerAssignmentService
from app.domain.services.transcription_service import ITranscriptionService
from app.infrastructure.database.repositories.sqlalchemy_task_repository import (
    AsyncSQLAlchemyTaskRepository,
)
from app.services.file_service import FileService
from app.services.task_management_service import TaskManagementService


# Global container instance - will be set by main.py
_container: Container | None = None


def set_container(container: Container) -> None:
    """Set the global container instance."""
    global _container
    _container = container


async def get_task_repository() -> AsyncGenerator[ITaskRepository, None]:
    """
    Provide a task repository implementation for dependency injection.

    Opens an AsyncSession for the duration of the request and closes it on
    teardown. The container's ``db_session_factory`` is used so that
    TestContainer overrides take effect in tests.

    Yields:
        ITaskRepository: A task repository implementation

    Example:
        >>> @router.post("/tasks")
        >>> async def create_task(
        ...     repository: Annotated[ITaskRepository, Depends(get_task_repository)]
        ... ):
        ...     task_id = await repository.add(task)
        ...     return {"id": task_id}
    """
    if _container is None:
        raise RuntimeError(CONTAINER_NOT_INITIALIZED_ERROR)
    async with _container.db_session_factory() as session:
        yield AsyncSQLAlchemyTaskRepository(session)


def get_file_service() -> Generator[FileService, None, None]:
    """
    Provide a FileService instance for dependency injection.

    FileService is stateless and registered as a singleton in the container,
    so the same instance is reused across all requests.

    Yields:
        FileService: A file service instance
    """
    if _container is None:
        raise RuntimeError(CONTAINER_NOT_INITIALIZED_ERROR)
    yield _container.file_service()


async def get_task_management_service() -> AsyncGenerator[TaskManagementService, None]:
    """
    Provide a TaskManagementService instance for dependency injection.

    Opens an AsyncSession, wraps it in a repository, and passes the repository
    to a fresh TaskManagementService. Session is closed after the request.

    Yields:
        TaskManagementService: A task management service instance
    """
    if _container is None:
        raise RuntimeError(CONTAINER_NOT_INITIALIZED_ERROR)
    async with _container.db_session_factory() as session:
        repo = AsyncSQLAlchemyTaskRepository(session)
        yield TaskManagementService(repo)


def get_transcription_service() -> Generator[ITranscriptionService, None, None]:
    """
    Provide a transcription service implementation for dependency injection.

    Returns WhisperX implementation from the container. Registered as a singleton
    for model caching and reuse. Can be overridden for testing by using
    container.override_providers().

    Yields:
        ITranscriptionService: A transcription service implementation

    Example:
        >>> @router.post("/transcribe")
        >>> async def transcribe(
        ...     transcription: Annotated[
        ...         ITranscriptionService,
        ...         Depends(get_transcription_service),
        ...     ]
        ... ):
        ...     result = transcription.transcribe(audio, params)
        ...     return result
    """
    if _container is None:
        raise RuntimeError(CONTAINER_NOT_INITIALIZED_ERROR)
    yield _container.transcription_service()


def get_diarization_service() -> Generator[IDiarizationService, None, None]:
    """
    Provide a diarization service implementation for dependency injection.

    Returns WhisperX/PyAnnote implementation from the container. Registered as
    a singleton for model caching and reuse. Can be overridden for testing
    by using container.override_providers().

    Yields:
        IDiarizationService: A diarization service implementation

    Example:
        >>> @router.post("/diarize")
        >>> async def diarize(
        ...     diarization: Annotated[
        ...         IDiarizationService,
        ...         Depends(get_diarization_service),
        ...     ]
        ... ):
        ...     result = diarization.diarize(audio, device)
        ...     return result
    """
    if _container is None:
        raise RuntimeError(CONTAINER_NOT_INITIALIZED_ERROR)
    yield _container.diarization_service()


def get_alignment_service() -> Generator[IAlignmentService, None, None]:
    """
    Provide an alignment service implementation for dependency injection.

    Returns WhisperX implementation from the container. Registered as a singleton
    for model caching and reuse. Can be overridden for testing by using
    container.override_providers().

    Yields:
        IAlignmentService: An alignment service implementation

    Example:
        >>> @router.post("/align")
        >>> async def align(
        ...     alignment: Annotated[
        ...         IAlignmentService,
        ...         Depends(get_alignment_service),
        ...     ]
        ... ):
        ...     result = alignment.align(transcript, audio, language)
        ...     return result
    """
    if _container is None:
        raise RuntimeError(CONTAINER_NOT_INITIALIZED_ERROR)
    yield _container.alignment_service()


def get_speaker_assignment_service() -> Generator[
    ISpeakerAssignmentService, None, None
]:
    """
    Provide a speaker assignment service implementation for dependency injection.

    Returns WhisperX implementation from the container. Registered as a singleton
    for consistency. Can be overridden for testing by using
    container.override_providers().

    Yields:
        ISpeakerAssignmentService: A speaker assignment service implementation

    Example:
        >>> @router.post("/assign-speakers")
        >>> async def assign_speakers(
        ...     speaker_service: Annotated[
        ...         ISpeakerAssignmentService,
        ...         Depends(get_speaker_assignment_service),
        ...     ]
        ... ):
        ...     result = speaker_service.assign_speakers(diarization, transcript)
        ...     return result
    """
    if _container is None:
        raise RuntimeError(CONTAINER_NOT_INITIALIZED_ERROR)
    yield _container.speaker_assignment_service()


TaskRepositoryDependency = Annotated[ITaskRepository, Depends(get_task_repository)]
FileServiceDependency = Annotated[FileService, Depends(get_file_service)]
TaskManagementServiceDependency = Annotated[
    TaskManagementService, Depends(get_task_management_service)
]
TranscriptionServiceDependency = Annotated[
    ITranscriptionService, Depends(get_transcription_service)
]
DiarizationServiceDependency = Annotated[
    IDiarizationService, Depends(get_diarization_service)
]
AlignmentServiceDependency = Annotated[
    IAlignmentService, Depends(get_alignment_service)
]
SpeakerAssignmentServiceDependency = Annotated[
    ISpeakerAssignmentService, Depends(get_speaker_assignment_service)
]
