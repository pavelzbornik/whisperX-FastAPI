"""Unit tests for AsyncSQLAlchemySpeakerEmbeddingRepository."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.domain.entities.speaker_embedding import SpeakerEmbedding
from app.infrastructure.database.repositories.sqlalchemy_speaker_embedding_repository import (
    AsyncSQLAlchemySpeakerEmbeddingRepository,
    SyncSQLAlchemySpeakerEmbeddingRepository,
)


@pytest.fixture
def async_session() -> AsyncMock:
    """Create a mock async session."""
    return AsyncMock()


@pytest.fixture
def async_repo(async_session: AsyncMock) -> AsyncSQLAlchemySpeakerEmbeddingRepository:
    """Create an async repository with mocked session."""
    return AsyncSQLAlchemySpeakerEmbeddingRepository(async_session)


class TestAsyncSQLAlchemySpeakerEmbeddingRepository:
    """Tests for async speaker embedding repository."""

    async def test_add_success(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test adding a speaker embedding."""
        embedding = SpeakerEmbedding(
            uuid="test-uuid",
            speaker_label="Alice",
            embedding=[0.1, 0.2],
        )
        result = await async_repo.add(embedding)
        assert result == "test-uuid"
        async_session.add.assert_called_once()
        async_session.commit.assert_awaited_once()

    async def test_add_rollback_on_error(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test add rolls back on SQLAlchemy error."""
        async_session.commit.side_effect = SQLAlchemyError("DB error")
        embedding = SpeakerEmbedding(
            uuid="test-uuid", speaker_label="Alice", embedding=[0.1]
        )
        with pytest.raises(Exception):
            await async_repo.add(embedding)
        async_session.rollback.assert_awaited_once()

    async def test_get_by_id_found(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test getting a speaker by UUID when it exists."""
        mock_orm = MagicMock()
        mock_orm.uuid = "u1"
        mock_orm.speaker_label = "Alice"
        mock_orm.description = None
        mock_orm.embedding = [0.1, 0.2]
        mock_orm.task_uuid = None
        mock_orm.created_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_orm
        async_session.execute.return_value = mock_result

        result = await async_repo.get_by_id("u1")
        assert result is not None
        assert result.uuid == "u1"
        assert result.speaker_label == "Alice"

    async def test_get_by_id_not_found(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test getting a nonexistent speaker returns None."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        async_session.execute.return_value = mock_result

        result = await async_repo.get_by_id("missing")
        assert result is None

    async def test_get_by_id_error(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test get_by_id raises on DB error."""
        async_session.execute.side_effect = SQLAlchemyError("DB error")
        with pytest.raises(Exception):
            await async_repo.get_by_id("u1")

    async def test_get_by_task(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test getting speakers by task UUID."""
        mock_orm = MagicMock()
        mock_orm.uuid = "u1"
        mock_orm.speaker_label = "Alice"
        mock_orm.description = None
        mock_orm.embedding = [0.1]
        mock_orm.task_uuid = "task-1"
        mock_orm.created_at = datetime.now(timezone.utc)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_orm]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        async_session.execute.return_value = mock_result

        result = await async_repo.get_by_task("task-1")
        assert len(result) == 1
        assert result[0].task_uuid == "task-1"

    async def test_get_by_task_error(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test get_by_task raises on DB error."""
        async_session.execute.side_effect = SQLAlchemyError("DB error")
        with pytest.raises(Exception):
            await async_repo.get_by_task("task-1")

    async def test_list_all(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test listing all speakers."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        async_session.execute.return_value = mock_result

        result = await async_repo.list_all(limit=10, offset=0)
        assert result == []

    async def test_list_all_error(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test list_all raises on DB error."""
        async_session.execute.side_effect = SQLAlchemyError("DB error")
        with pytest.raises(Exception):
            await async_repo.list_all()

    async def test_update_found(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test updating an existing speaker."""
        mock_orm = MagicMock()
        mock_orm.speaker_label = "Old"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_orm
        async_session.execute.return_value = mock_result

        result = await async_repo.update("u1", {"speaker_label": "New"})
        assert result is True
        async_session.commit.assert_awaited_once()

    async def test_update_not_found(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test updating a nonexistent speaker returns False."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        async_session.execute.return_value = mock_result

        result = await async_repo.update("missing", {"speaker_label": "X"})
        assert result is False

    async def test_update_error(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test update raises on DB error."""
        async_session.execute.side_effect = SQLAlchemyError("DB error")
        with pytest.raises(Exception):
            await async_repo.update("u1", {"speaker_label": "X"})

    async def test_delete_found(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test deleting an existing speaker."""
        mock_orm = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_orm
        async_session.execute.return_value = mock_result

        result = await async_repo.delete("u1")
        assert result is True
        async_session.delete.assert_awaited_once_with(mock_orm)
        async_session.commit.assert_awaited_once()

    async def test_delete_not_found(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test deleting a nonexistent speaker returns False."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        async_session.execute.return_value = mock_result

        result = await async_repo.delete("missing")
        assert result is False

    async def test_delete_error(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test delete raises on DB error."""
        async_session.execute.side_effect = SQLAlchemyError("DB error")
        with pytest.raises(Exception):
            await async_repo.delete("u1")

    async def test_delete_by_task(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test deleting all speakers for a task."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        async_session.execute.return_value = mock_result

        result = await async_repo.delete_by_task("task-1")
        assert result == 3
        async_session.commit.assert_awaited_once()

    async def test_delete_by_task_error(
        self,
        async_repo: AsyncSQLAlchemySpeakerEmbeddingRepository,
        async_session: AsyncMock,
    ) -> None:
        """Test delete_by_task raises on DB error."""
        async_session.execute.side_effect = SQLAlchemyError("DB error")
        with pytest.raises(Exception):
            await async_repo.delete_by_task("task-1")


class TestSyncSQLAlchemySpeakerEmbeddingRepository:
    """Tests for sync speaker embedding repository."""

    def test_add_batch(self) -> None:
        """Test adding multiple embeddings."""
        mock_session = MagicMock()
        repo = SyncSQLAlchemySpeakerEmbeddingRepository(mock_session)

        embeddings = [
            SpeakerEmbedding(uuid="u1", speaker_label="A", embedding=[0.1]),
            SpeakerEmbedding(uuid="u2", speaker_label="B", embedding=[0.2]),
        ]
        result = repo.add_batch(embeddings)
        assert result == ["u1", "u2"]
        assert mock_session.add.call_count == 2
        mock_session.commit.assert_called_once()

    def test_add_batch_rollback_on_error(self) -> None:
        """Test add_batch rolls back on error."""
        mock_session = MagicMock()
        mock_session.commit.side_effect = SQLAlchemyError("DB error")
        repo = SyncSQLAlchemySpeakerEmbeddingRepository(mock_session)

        embeddings = [
            SpeakerEmbedding(uuid="u1", speaker_label="A", embedding=[0.1]),
        ]
        with pytest.raises(Exception):
            repo.add_batch(embeddings)
        mock_session.rollback.assert_called_once()

    def test_get_all(self) -> None:
        """Test getting all embeddings."""
        mock_session = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        repo = SyncSQLAlchemySpeakerEmbeddingRepository(mock_session)
        result = repo.get_all()
        assert result == []

    def test_get_all_error(self) -> None:
        """Test get_all raises on DB error."""
        mock_session = MagicMock()
        mock_session.execute.side_effect = SQLAlchemyError("DB error")
        repo = SyncSQLAlchemySpeakerEmbeddingRepository(mock_session)

        with pytest.raises(Exception):
            repo.get_all()
