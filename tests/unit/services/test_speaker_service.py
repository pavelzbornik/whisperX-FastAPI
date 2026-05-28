"""Unit tests for SpeakerService."""

from unittest.mock import AsyncMock

import pytest

from app.domain.entities.speaker_embedding import SpeakerEmbedding
from app.services.speaker_service import SpeakerService


@pytest.fixture
def mock_repo() -> AsyncMock:
    """Create a mock speaker embedding repository."""
    return AsyncMock()


@pytest.fixture
def service(mock_repo: AsyncMock) -> SpeakerService:
    """Create a SpeakerService with mocked repository."""
    return SpeakerService(mock_repo)


class TestSpeakerServiceCRUD:
    """Test CRUD operations."""

    async def test_create(self, service: SpeakerService, mock_repo: AsyncMock) -> None:
        """Test creating a speaker embedding."""
        mock_repo.add.return_value = "test-uuid"
        uuid = await service.create(
            speaker_label="Alice",
            embedding=[0.1, 0.2],
            description="Manager",
            task_uuid="task-1",
        )
        assert uuid == "test-uuid"
        mock_repo.add.assert_called_once()
        created = mock_repo.add.call_args[0][0]
        assert created.speaker_label == "Alice"
        assert created.embedding == [0.1, 0.2]
        assert created.description == "Manager"
        assert created.task_uuid == "task-1"

    async def test_get_by_id(
        self, service: SpeakerService, mock_repo: AsyncMock
    ) -> None:
        """Test getting a speaker by UUID."""
        expected = SpeakerEmbedding(uuid="u1", speaker_label="Bob", embedding=[0.1])
        mock_repo.get_by_id.return_value = expected
        result = await service.get_by_id("u1")
        assert result == expected

    async def test_get_by_id_not_found(
        self, service: SpeakerService, mock_repo: AsyncMock
    ) -> None:
        """Test getting a nonexistent speaker returns None."""
        mock_repo.get_by_id.return_value = None
        result = await service.get_by_id("missing")
        assert result is None

    async def test_list_all(
        self, service: SpeakerService, mock_repo: AsyncMock
    ) -> None:
        """Test listing speakers with pagination."""
        mock_repo.list_all.return_value = []
        result = await service.list_all(limit=10, offset=5)
        assert result == []
        mock_repo.list_all.assert_called_once_with(limit=10, offset=5)

    async def test_update(self, service: SpeakerService, mock_repo: AsyncMock) -> None:
        """Test updating a speaker."""
        mock_repo.update.return_value = True
        result = await service.update("u1", {"speaker_label": "Charlie"})
        assert result is True

    async def test_delete(self, service: SpeakerService, mock_repo: AsyncMock) -> None:
        """Test deleting a speaker."""
        mock_repo.delete.return_value = True
        result = await service.delete("u1")
        assert result is True

    async def test_delete_by_task(
        self, service: SpeakerService, mock_repo: AsyncMock
    ) -> None:
        """Test deleting speakers by task."""
        mock_repo.delete_by_task.return_value = 3
        result = await service.delete_by_task("task-1")
        assert result == 3


class TestSpeakerServiceSearch:
    """Test search and identification."""

    async def test_search_similar_finds_matches(
        self, service: SpeakerService, mock_repo: AsyncMock
    ) -> None:
        """Test cosine similarity search returns matches above threshold."""
        alice = SpeakerEmbedding(
            uuid="a", speaker_label="Alice", embedding=[1.0, 0.0, 0.0]
        )
        bob = SpeakerEmbedding(uuid="b", speaker_label="Bob", embedding=[0.0, 1.0, 0.0])
        mock_repo.list_all.return_value = [alice, bob]

        results = await service.search_similar(
            embedding=[0.9, 0.1, 0.0], limit=5, threshold=0.5
        )
        assert len(results) >= 1
        # Alice should be the best match (most similar to [0.9, 0.1, 0.0])
        assert results[0][0].speaker_label == "Alice"
        assert results[0][1] > 0.9

    async def test_search_similar_empty_db(
        self, service: SpeakerService, mock_repo: AsyncMock
    ) -> None:
        """Test search with empty database returns nothing."""
        mock_repo.list_all.return_value = []
        results = await service.search_similar(
            embedding=[1.0, 0.0], limit=5, threshold=0.5
        )
        assert results == []

    async def test_search_similar_zero_query(
        self, service: SpeakerService, mock_repo: AsyncMock
    ) -> None:
        """Test search with zero vector returns nothing."""
        mock_repo.list_all.return_value = [
            SpeakerEmbedding(uuid="a", speaker_label="A", embedding=[1.0])
        ]
        results = await service.search_similar(embedding=[0.0], limit=5, threshold=0.0)
        assert results == []

    async def test_search_similar_respects_threshold(
        self, service: SpeakerService, mock_repo: AsyncMock
    ) -> None:
        """Test that results below threshold are excluded."""
        alice = SpeakerEmbedding(uuid="a", speaker_label="Alice", embedding=[1.0, 0.0])
        mock_repo.list_all.return_value = [alice]

        # Orthogonal vector should have ~0 similarity
        results = await service.search_similar(
            embedding=[0.0, 1.0], limit=5, threshold=0.5
        )
        assert len(results) == 0

    async def test_identify_returns_best_match(
        self, service: SpeakerService, mock_repo: AsyncMock
    ) -> None:
        """Test identify returns the single best match."""
        alice = SpeakerEmbedding(uuid="a", speaker_label="Alice", embedding=[1.0, 0.0])
        mock_repo.list_all.return_value = [alice]

        result = await service.identify(embedding=[0.95, 0.05], threshold=0.5)
        assert result is not None
        assert result[0].speaker_label == "Alice"

    async def test_identify_returns_none_below_threshold(
        self, service: SpeakerService, mock_repo: AsyncMock
    ) -> None:
        """Test identify returns None when no match above threshold."""
        alice = SpeakerEmbedding(uuid="a", speaker_label="Alice", embedding=[1.0, 0.0])
        mock_repo.list_all.return_value = [alice]

        result = await service.identify(embedding=[0.0, 1.0], threshold=0.9)
        assert result is None
