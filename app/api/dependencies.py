"""Dependency injection providers for FastAPI endpoints."""

from collections.abc import Generator

from fastapi import BackgroundTasks

from app.core.container import Container
from app.domain.repositories.task_repository import ITaskRepository
from app.domain.services.alignment_service import IAlignmentService
from app.domain.services.diarization_service import IDiarizationService
from app.domain.services.speaker_assignment_service import ISpeakerAssignmentService
from app.domain.services.transcription_service import ITranscriptionService
from app.infrastructure.tasks.fastapi_task_queue import FastAPITaskQueue
from app.infrastructure.tasks.task_registry import TaskRegistry
from app.services.file_service import FileService
from app.services.task_management_service import TaskManagementService


# Global container instance - will be set by main.py
_container: Container | None = None


def set_container(container: Container) -> None:
    """Set the global container instance."""
    global _container
    _container = container


def get_task_repository() -> Generator[ITaskRepository, None, None]:
    """
    Provide a task repository implementation for dependency injection.

    This function uses the container to provide a task repository instance
    with a managed database session. The container ensures proper lifecycle
    management of both the session and repository.

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
    if _container is None:
        raise RuntimeError("Container not initialized. Call set_container() first.")
    yield _container.task_repository()


def get_file_service() -> Generator[FileService, None, None]:
    """
    Provide a FileService instance for dependency injection.

    FileService is stateless and registered as a singleton in the container,
    so the same instance is reused across all requests.

    Yields:
        FileService: A file service instance
    """
    if _container is None:
        raise RuntimeError("Container not initialized. Call set_container() first.")
    yield _container.file_service()


def get_task_management_service() -> Generator[TaskManagementService, None, None]:
    """
    Provide a TaskManagementService instance for dependency injection.

    The service is initialized with a task repository from the container.
    Registered as a factory, so a new instance is created for each request.

    Yields:
        TaskManagementService: A task management service instance
    """
    if _container is None:
        raise RuntimeError("Container not initialized. Call set_container() first.")
    yield _container.task_management_service()


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
        ...     transcription: ITranscriptionService = Depends(get_transcription_service)
        ... ):
        ...     result = transcription.transcribe(audio, params)
        ...     return result
    """
    if _container is None:
        raise RuntimeError("Container not initialized. Call set_container() first.")
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
        ...     diarization: IDiarizationService = Depends(get_diarization_service)
        ... ):
        ...     result = diarization.diarize(audio, device)
        ...     return result
    """
    if _container is None:
        raise RuntimeError("Container not initialized. Call set_container() first.")
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
        ...     alignment: IAlignmentService = Depends(get_alignment_service)
        ... ):
        ...     result = alignment.align(transcript, audio, language)
        ...     return result
    """
    if _container is None:
        raise RuntimeError("Container not initialized. Call set_container() first.")
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
        ...     speaker_service: ISpeakerAssignmentService = Depends(get_speaker_assignment_service)
        ... ):
        ...     result = speaker_service.assign_speakers(diarization, transcript)
        ...     return result
    """
    if _container is None:
        raise RuntimeError("Container not initialized. Call set_container() first.")
    yield _container.speaker_assignment_service()


def get_task_registry() -> Generator[TaskRegistry, None, None]:
    """
    Provide the task registry for dependency injection.

    The task registry is a singleton that maintains the mapping of task types
    to handler functions. It should be initialized once during application
    startup with all available handlers.

    Yields:
        TaskRegistry: The task registry singleton

    Example:
        >>> @router.get("/task-types")
        >>> async def list_task_types(
        ...     registry: TaskRegistry = Depends(get_task_registry)
        ... ):
        ...     return {"task_types": registry.list_task_types()}
    """
    if _container is None:
        raise RuntimeError("Container not initialized. Call set_container() first.")
    yield _container.task_registry()


def get_task_queue(
    background_tasks: BackgroundTasks,
) -> Generator[FastAPITaskQueue, None, None]:
    """
    Provide a task queue implementation for dependency injection.

    This creates a FastAPITaskQueue instance that wraps the provided
    BackgroundTasks from FastAPI. The task queue provides a consistent
    interface for background task processing that can be swapped with
    distributed queue implementations (Celery, RQ) in the future.

    Args:
        background_tasks: FastAPI BackgroundTasks from the request context

    Yields:
        FastAPITaskQueue: Task queue implementation

    Example:
        >>> @router.post("/process")
        >>> async def process_task(
        ...     background_tasks: BackgroundTasks,
        ...     task_queue: FastAPITaskQueue = Depends(get_task_queue)
        ... ):
        ...     task_id = task_queue.enqueue(
        ...         task_type="audio_processing",
        ...         parameters={"file_path": "/tmp/audio.mp3"}
        ...     )
        ...     return {"task_id": task_id}
    """
    if _container is None:
        raise RuntimeError("Container not initialized. Call set_container() first.")

    # Create task executor and repository from container
    task_executor = _container.task_executor()
    task_repository = _container.task_repository()

    # Create and yield the task queue
    yield FastAPITaskQueue(
        background_tasks=background_tasks,
        task_executor=task_executor,
        task_repository=task_repository,
    )
