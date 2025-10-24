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
