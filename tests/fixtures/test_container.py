"""Test container with mock implementations for testing."""

from dependency_injector import providers
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.container import Container
from tests.mocks import (
    MockAlignmentService,
    MockDiarizationService,
    MockSpeakerAssignmentService,
    MockTranscriptionService,
)

_test_async_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    poolclass=NullPool,
)
_test_session_factory = async_sessionmaker(
    _test_async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class TestContainer(Container):
    """
    Test container that overrides production services with mocks.

    This container extends the production Container and overrides:
    - ML services with fast, deterministic mocks (no GPU, no network)
    - Database with in-memory async SQLite for isolated testing
    - All other services remain the same (repositories, file service, etc.)

    Usage in tests:
        >>> test_container = TestContainer()
        >>> test_container.wire(modules=["app.api.dependencies"])
        >>> # Run tests with mocked services
        >>> test_container.unwire()

    Example with pytest fixture:
        >>> @pytest.fixture
        >>> def test_container():
        ...     container = TestContainer()
        ...     yield container
        ...     # Cleanup happens automatically
    """

    # Override database with in-memory async SQLite for test isolation
    db_engine = providers.Singleton(lambda: _test_async_engine)
    db_session_factory = providers.Factory(_test_session_factory)

    # Override ML services with fast mocks (no GPU, no network calls)
    transcription_service = providers.Singleton(MockTranscriptionService)

    diarization_service = providers.Singleton(
        MockDiarizationService,
        hf_token="mock_token",
    )

    alignment_service = providers.Singleton(MockAlignmentService)

    speaker_assignment_service = providers.Singleton(MockSpeakerAssignmentService)

    # All other services (repositories, file service, task management) inherit from Container
    # and work normally with the test database
