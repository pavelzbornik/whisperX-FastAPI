"""Test container with mock implementations for testing."""

from dependency_injector import providers
from sqlalchemy import create_engine

from app.core.container import Container
from tests.mocks import (
    MockAlignmentService,
    MockDiarizationService,
    MockSpeakerAssignmentService,
    MockTranscriptionService,
)


class TestContainer(Container):
    """
    Test container that overrides production services with mocks.

    This container extends the production Container and overrides:
    - ML services with fast, deterministic mocks (no GPU, no network)
    - Database with in-memory SQLite for isolated testing
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

    # Override database with in-memory SQLite for test isolation
    db_engine = providers.Singleton(
        create_engine,
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )

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
