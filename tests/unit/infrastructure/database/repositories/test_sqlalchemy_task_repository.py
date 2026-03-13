"""Unit tests for AsyncSQLAlchemyTaskRepository and SyncSQLAlchemyTaskRepository."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import DatabaseOperationError
from app.infrastructure.database.models import Task as ORMTask
from app.infrastructure.database.repositories.sqlalchemy_task_repository import (
    AsyncSQLAlchemyTaskRepository,
    SyncSQLAlchemyTaskRepository,
)
from tests.factories import TaskFactory


@pytest.mark.unit
class TestAsyncSQLAlchemyTaskRepository:
    """Unit tests for AsyncSQLAlchemyTaskRepository."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def repository(self, mock_session: AsyncMock) -> AsyncSQLAlchemyTaskRepository:
        """Create a repository instance with mock session."""
        return AsyncSQLAlchemyTaskRepository(mock_session)

    @patch("app.infrastructure.database.repositories.sqlalchemy_task_repository.to_orm")
    async def test_add_creates_task_successfully(
        self,
        mock_to_orm: Mock,
        repository: AsyncSQLAlchemyTaskRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test adding a task successfully."""
        task = TaskFactory(uuid="test-123")
        orm_task = MagicMock(spec=ORMTask)
        orm_task.uuid = "test-123"
        mock_to_orm.return_value = orm_task

        result = await repository.add(task)

        assert result == "test-123"
        mock_to_orm.assert_called_once_with(task)
        mock_session.add.assert_called_once_with(orm_task)
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(orm_task)

    @patch("app.infrastructure.database.repositories.sqlalchemy_task_repository.to_orm")
    async def test_add_generates_uuid_if_missing(
        self,
        mock_to_orm: Mock,
        repository: AsyncSQLAlchemyTaskRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test adding a task without UUID generates one."""
        task = TaskFactory(uuid="")
        orm_task = MagicMock(spec=ORMTask)
        orm_task.uuid = "generated-uuid"
        mock_to_orm.return_value = orm_task

        result = await repository.add(task)

        assert task.uuid != ""
        assert result == "generated-uuid"

    @patch("app.infrastructure.database.repositories.sqlalchemy_task_repository.to_orm")
    async def test_add_rolls_back_on_error(
        self,
        mock_to_orm: Mock,
        repository: AsyncSQLAlchemyTaskRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test add rolls back transaction on error."""
        task = TaskFactory()
        mock_to_orm.return_value = MagicMock(spec=ORMTask)
        mock_session.commit.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(DatabaseOperationError) as exc_info:
            await repository.add(task)

        assert exc_info.value.details["operation"] == "add"
        assert "Database error" in exc_info.value.details["reason"]
        mock_session.rollback.assert_awaited_once()

    @patch(
        "app.infrastructure.database.repositories.sqlalchemy_task_repository.to_domain"
    )
    async def test_get_by_id_returns_task_when_found(
        self,
        mock_to_domain: Mock,
        repository: AsyncSQLAlchemyTaskRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test get_by_id returns task when found."""
        orm_task = MagicMock(spec=ORMTask)
        domain_task = TaskFactory(uuid="test-123")

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = orm_task
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_to_domain.return_value = domain_task

        result = await repository.get_by_id("test-123")

        assert result == domain_task
        mock_to_domain.assert_called_once_with(orm_task)

    async def test_get_by_id_returns_none_when_not_found(
        self,
        repository: AsyncSQLAlchemyTaskRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test get_by_id returns None when task not found."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_by_id("non-existent")

        assert result is None

    async def test_get_by_id_returns_none_on_error(
        self,
        repository: AsyncSQLAlchemyTaskRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test get_by_id returns None on database error."""
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        result = await repository.get_by_id("test-123")

        assert result is None

    @patch(
        "app.infrastructure.database.repositories.sqlalchemy_task_repository.to_domain"
    )
    async def test_get_all_returns_all_tasks(
        self,
        mock_to_domain: Mock,
        repository: AsyncSQLAlchemyTaskRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test get_all returns all tasks."""
        orm_task1 = MagicMock(spec=ORMTask)
        orm_task2 = MagicMock(spec=ORMTask)
        domain_task1 = TaskFactory(uuid="task-1")
        domain_task2 = TaskFactory(uuid="task-2")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [orm_task1, orm_task2]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_to_domain.side_effect = [domain_task1, domain_task2]

        result = await repository.get_all()

        assert len(result) == 2
        assert domain_task1 in result
        assert domain_task2 in result

    async def test_get_all_returns_empty_list_when_no_tasks(
        self,
        repository: AsyncSQLAlchemyTaskRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test get_all returns empty list when no tasks exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_all()

        assert result == []

    @patch(
        "app.infrastructure.database.repositories.sqlalchemy_task_repository.to_domain"
    )
    async def test_update_updates_task_successfully(
        self,
        mock_to_domain: Mock,
        repository: AsyncSQLAlchemyTaskRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test updating a task successfully."""
        orm_task = MagicMock(spec=ORMTask)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = orm_task
        mock_session.execute = AsyncMock(return_value=mock_result)

        update_data = {
            "status": "completed",
            "result": {"text": "updated"},
            "duration": 15.5,
        }

        await repository.update("test-123", update_data)

        assert orm_task.status == "completed"
        assert orm_task.result == {"text": "updated"}
        assert orm_task.duration == pytest.approx(15.5)
        mock_session.commit.assert_awaited_once()

    async def test_update_raises_when_task_not_found(
        self,
        repository: AsyncSQLAlchemyTaskRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test update raises ValueError when task doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Task not found"):
            await repository.update("non-existent", {"status": "completed"})

        mock_session.commit.assert_not_awaited()

    async def test_update_rolls_back_on_error(
        self,
        repository: AsyncSQLAlchemyTaskRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test update rolls back transaction on database error."""
        orm_task = MagicMock(spec=ORMTask)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = orm_task
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(DatabaseOperationError) as exc_info:
            await repository.update("test-123", {"status": "completed"})

        assert exc_info.value.details["operation"] == "update"
        assert "Database error" in exc_info.value.details["reason"]
        assert exc_info.value.details["identifier"] == "test-123"
        mock_session.rollback.assert_awaited_once()

    async def test_delete_removes_task_successfully(
        self,
        repository: AsyncSQLAlchemyTaskRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test deleting a task successfully."""
        orm_task = MagicMock(spec=ORMTask)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = orm_task
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.delete("test-123")

        assert result is True
        mock_session.delete.assert_awaited_once_with(orm_task)
        mock_session.commit.assert_awaited_once()

    async def test_delete_returns_false_when_task_not_found(
        self,
        repository: AsyncSQLAlchemyTaskRepository,
        mock_session: AsyncMock,
    ) -> None:
        """Test delete returns False when task doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.delete("non-existent")

        assert result is False
        mock_session.delete.assert_not_awaited()
        mock_session.commit.assert_not_awaited()


@pytest.mark.unit
class TestSyncSQLAlchemyTaskRepository:
    """Unit tests for SyncSQLAlchemyTaskRepository (used by background tasks)."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock sync database session."""
        return MagicMock()

    @pytest.fixture
    def repository(self, mock_session: MagicMock) -> SyncSQLAlchemyTaskRepository:
        """Create a sync repository instance with mock session."""
        return SyncSQLAlchemyTaskRepository(mock_session)

    @patch("app.infrastructure.database.repositories.sqlalchemy_task_repository.to_orm")
    def test_add_creates_task_successfully(
        self,
        mock_to_orm: Mock,
        repository: SyncSQLAlchemyTaskRepository,
        mock_session: MagicMock,
    ) -> None:
        """Test adding a task successfully."""
        task = TaskFactory(uuid="test-123")
        orm_task = MagicMock(spec=ORMTask)
        orm_task.uuid = "test-123"
        mock_to_orm.return_value = orm_task

        result = repository.add(task)

        assert result == "test-123"
        mock_session.add.assert_called_once_with(orm_task)
        mock_session.commit.assert_called_once()

    @patch("app.infrastructure.database.repositories.sqlalchemy_task_repository.to_orm")
    def test_add_rolls_back_on_error(
        self,
        mock_to_orm: Mock,
        repository: SyncSQLAlchemyTaskRepository,
        mock_session: MagicMock,
    ) -> None:
        """Test add rolls back transaction on error."""
        task = TaskFactory()
        mock_to_orm.return_value = MagicMock(spec=ORMTask)
        mock_session.commit.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(DatabaseOperationError):
            repository.add(task)

        mock_session.rollback.assert_called_once()

    @patch(
        "app.infrastructure.database.repositories.sqlalchemy_task_repository.to_domain"
    )
    def test_get_by_id_returns_task_when_found(
        self,
        mock_to_domain: Mock,
        repository: SyncSQLAlchemyTaskRepository,
        mock_session: MagicMock,
    ) -> None:
        """Test get_by_id returns task when found."""
        orm_task = MagicMock(spec=ORMTask)
        domain_task = TaskFactory(uuid="test-123")
        mock_session.query.return_value.filter.return_value.first.return_value = (
            orm_task
        )
        mock_to_domain.return_value = domain_task

        result = repository.get_by_id("test-123")

        assert result == domain_task

    def test_get_by_id_returns_none_when_not_found(
        self, repository: SyncSQLAlchemyTaskRepository, mock_session: MagicMock
    ) -> None:
        """Test get_by_id returns None when task not found."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = repository.get_by_id("non-existent")

        assert result is None

    @patch(
        "app.infrastructure.database.repositories.sqlalchemy_task_repository.to_domain"
    )
    def test_get_all_returns_all_tasks(
        self,
        mock_to_domain: Mock,
        repository: SyncSQLAlchemyTaskRepository,
        mock_session: MagicMock,
    ) -> None:
        """Test get_all returns all tasks."""
        orm_task = MagicMock(spec=ORMTask)
        domain_task = TaskFactory(uuid="task-1")
        mock_session.query.return_value.all.return_value = [orm_task]
        mock_to_domain.return_value = domain_task

        result = repository.get_all()

        assert len(result) == 1

    def test_update_updates_task_successfully(
        self, repository: SyncSQLAlchemyTaskRepository, mock_session: MagicMock
    ) -> None:
        """Test updating a task successfully."""
        orm_task = MagicMock(spec=ORMTask)
        mock_session.query.return_value.filter.return_value.first.return_value = (
            orm_task
        )

        repository.update("test-123", {"status": "completed"})

        mock_session.commit.assert_called_once()

    def test_update_raises_when_task_not_found(
        self, repository: SyncSQLAlchemyTaskRepository, mock_session: MagicMock
    ) -> None:
        """Test update raises ValueError when task doesn't exist."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="Task not found"):
            repository.update("non-existent", {"status": "completed"})

    def test_delete_removes_task_successfully(
        self, repository: SyncSQLAlchemyTaskRepository, mock_session: MagicMock
    ) -> None:
        """Test deleting a task successfully."""
        orm_task = MagicMock(spec=ORMTask)
        mock_session.query.return_value.filter.return_value.first.return_value = (
            orm_task
        )

        result = repository.delete("test-123")

        assert result is True
        mock_session.delete.assert_called_once_with(orm_task)
        mock_session.commit.assert_called_once()

    def test_delete_returns_false_when_task_not_found(
        self, repository: SyncSQLAlchemyTaskRepository, mock_session: MagicMock
    ) -> None:
        """Test delete returns False when task doesn't exist."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = repository.delete("non-existent")

        assert result is False
