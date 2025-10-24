"""Tests for dependency injection container."""

from app.core.container import Container
from tests.fixtures import TestContainer


class TestDependencyContainer:
    """Test dependency injection container functionality."""

    def test_container_creation(self) -> None:
        """Test that container can be created successfully."""
        container = Container()
        assert container is not None

    def test_container_provides_config(self) -> None:
        """Test that container provides configuration."""
        container = Container()
        config = container.config()
        assert config is not None
        assert hasattr(config, "whisper")
        assert hasattr(config, "database")

    def test_container_provides_file_service(self) -> None:
        """Test that container provides file service as singleton."""
        container = Container()
        service1 = container.file_service()
        service2 = container.file_service()
        # Singletons should return same instance
        assert service1 is service2

    def test_container_provides_task_repository(self) -> None:
        """Test that container provides task repository."""
        container = Container()
        repo = container.task_repository()
        assert repo is not None

    def test_container_provides_ml_services(self) -> None:
        """Test that container provides all ML services."""
        container = Container()

        transcription = container.transcription_service()
        diarization = container.diarization_service()
        alignment = container.alignment_service()
        speaker = container.speaker_assignment_service()

        assert transcription is not None
        assert diarization is not None
        assert alignment is not None
        assert speaker is not None

    def test_ml_services_are_singletons(self) -> None:
        """Test that ML services are singletons for model caching."""
        container = Container()

        # Get services twice
        trans1 = container.transcription_service()
        trans2 = container.transcription_service()

        # Should be same instance (singleton)
        assert trans1 is trans2


class TestContainerInTests:
    """Test container fixture for testing."""

    def test_test_container_creation(self, test_container: TestContainer) -> None:
        """Test that test container fixture works."""
        assert test_container is not None

    def test_test_container_provides_mocks(self, test_container: TestContainer) -> None:
        """Test that test container provides mock services."""
        # Get mock transcription service
        service = test_container.transcription_service()
        assert service is not None

        # Verify it's the mock (has mock behavior)
        # Mock services should be fast and not require GPU
        assert service.__class__.__name__ == "MockTranscriptionService"
