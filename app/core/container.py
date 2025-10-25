"""Dependency injection container for managing application dependencies."""

from dependency_injector import containers, providers

from app.core.config import get_settings
from app.infrastructure.database.connection import SessionLocal, engine
from app.infrastructure.database.repositories.sqlalchemy_task_repository import (
    SQLAlchemyTaskRepository,
)
from app.infrastructure.ml import (
    WhisperXAlignmentService,
    WhisperXDiarizationService,
    WhisperXSpeakerAssignmentService,
    WhisperXTranscriptionService,
)
from app.infrastructure.tasks.fastapi_task_queue import FastAPITaskQueue
from app.infrastructure.tasks.handlers.audio_processing_handler import (
    create_audio_processing_handler,
)
from app.infrastructure.tasks.task_executor import TaskExecutor
from app.infrastructure.tasks.task_registry import TaskRegistry
from app.services.file_service import FileService
from app.services.task_management_service import TaskManagementService


class Container(containers.DeclarativeContainer):
    """
    Dependency injection container for application services.

    This container manages the lifecycle and dependencies of all application
    components including configuration, database connections, repositories,
    services, and ML models.

    Architecture:
        - Configuration: Singleton settings instance
        - Database: Singleton engine, factory sessions
        - Repositories: Factory instances with session dependencies
        - Services: Mix of singletons (stateless) and factories (stateful)
        - ML Services: Singletons for model caching and reuse

    Lifecycle Management:
        - Singleton: Created once and reused (Config, FileService, ML Services)
        - Factory: New instance per request (Services with database sessions)
        - Resource: Managed lifecycle with init/cleanup (Database connections)

    Example:
        >>> container = Container()
        >>> container.wire(modules=["app.api.dependencies"])
        >>> # Services are now available via dependency injection
        >>> # Clean up on shutdown
        >>> container.unwire()
    """

    # Configuration - Singleton for application settings
    config = providers.Singleton(get_settings)

    # Database - Singleton engine, factory for sessions
    db_engine = providers.Singleton(lambda: engine)
    db_session_factory = providers.Factory(SessionLocal)

    # Repositories - Factory pattern with session dependency
    task_repository = providers.Factory(
        SQLAlchemyTaskRepository,
        session=db_session_factory,
    )

    # Services - Stateless services are singletons
    file_service = providers.Singleton(FileService)

    # Services - Stateful services are factories
    task_management_service = providers.Factory(
        TaskManagementService,
        repository=task_repository,
    )

    # ML Services - Singletons for model caching and reuse
    # These services load heavy ML models and should be reused
    transcription_service = providers.Singleton(
        WhisperXTranscriptionService,
    )

    diarization_service = providers.Singleton(
        WhisperXDiarizationService,
        hf_token=config.provided.whisper.HF_TOKEN,
    )

    alignment_service = providers.Singleton(
        WhisperXAlignmentService,
    )

    speaker_assignment_service = providers.Singleton(
        WhisperXSpeakerAssignmentService,
    )

    # Task Queue Infrastructure - For background task processing
    # Task registry - Singleton for centralized handler management
    task_registry = providers.Singleton(TaskRegistry)

    # Task executor - Factory pattern with dependencies
    task_executor = providers.Factory(
        TaskExecutor,
        task_registry=task_registry,
        task_repository=task_repository,
    )

    # Audio processing handlers - Factory that creates handler dictionary
    audio_handlers = providers.Factory(
        create_audio_processing_handler,
        transcription_service=transcription_service,
        diarization_service=diarization_service,
        alignment_service=alignment_service,
        speaker_service=speaker_assignment_service,
    )

    # Task queue - Factory pattern (requires BackgroundTasks from FastAPI)
    # Note: The actual FastAPITaskQueue will be created in dependencies with BackgroundTasks
    # This is a callable factory that will be invoked with background_tasks parameter
    task_queue_factory = providers.Callable(
        lambda background_tasks, task_executor, task_repository: FastAPITaskQueue(
            background_tasks=background_tasks,
            task_executor=task_executor,
            task_repository=task_repository,
        )
    )
