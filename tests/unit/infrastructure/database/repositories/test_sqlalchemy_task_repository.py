"""Unit tests for SQLAlchemyTaskRepository."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.database.models import Task as ORMTask
from app.infrastructure.database.repositories.sqlalchemy_task_repository import (
    SQLAlchemyTaskRepository,
)
from tests.factories import TaskFactory


@pytest.mark.unit
class TestSQLAlchemyTaskRepository:
    """Unit tests for SQLAlchemyTaskRepository."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def repository(self, mock_session: MagicMock) -> SQLAlchemyTaskRepository:
        """Create a repository instance with mock session."""
        return SQLAlchemyTaskRepository(mock_session)

    @patch("app.infrastructure.database.repositories.sqlalchemy_task_repository.to_orm")
    def test_add_creates_task_successfully(
        self,
        mock_to_orm: Mock,
        repository: SQLAlchemyTaskRepository,
        mock_session: MagicMock,
    ) -> None:
        """Test adding a task successfully."""
        task = TaskFactory(uuid="test-123")
        orm_task = MagicMock(spec=ORMTask)
        orm_task.uuid = "test-123"
        mock_to_orm.return_value = orm_task

        result = repository.add(task)

        assert result == "test-123"
        mock_to_orm.assert_called_once_with(task)
        mock_session.add.assert_called_once_with(orm_task)
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once_with(orm_task)

    @patch("app.infrastructure.database.repositories.sqlalchemy_task_repository.to_orm")
    def test_add_generates_uuid_if_missing(
        self,
        mock_to_orm: Mock,
        repository: SQLAlchemyTaskRepository,
        mock_session: MagicMock,
    ) -> None:
        """Test adding a task without UUID generates one."""
        task = TaskFactory(uuid="")
        orm_task = MagicMock(spec=ORMTask)
        orm_task.uuid = "generated-uuid"
        mock_to_orm.return_value = orm_task

        result = repository.add(task)

        # Task UUID should have been set
        assert task.uuid != ""
        assert result == "generated-uuid"

    @patch("app.infrastructure.database.repositories.sqlalchemy_task_repository.to_orm")
    def test_add_rolls_back_on_error(
        self,
        mock_to_orm: Mock,
        repository: SQLAlchemyTaskRepository,
        mock_session: MagicMock,
    ) -> None:
        """Test add rolls back transaction on error."""
        task = TaskFactory()
        mock_to_orm.return_value = MagicMock(spec=ORMTask)
        mock_session.commit.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(Exception, match="Failed to add task"):
            repository.add(task)

        mock_session.rollback.assert_called_once()

    @patch(
        "app.infrastructure.database.repositories.sqlalchemy_task_repository.to_domain"
    )
    def test_get_by_id_returns_task_when_found(
        self,
        mock_to_domain: Mock,
        repository: SQLAlchemyTaskRepository,
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
        mock_to_domain.assert_called_once_with(orm_task)

    def test_get_by_id_returns_none_when_not_found(
        self, repository: SQLAlchemyTaskRepository, mock_session: MagicMock
    ) -> None:
        """Test get_by_id returns None when task not found."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = repository.get_by_id("non-existent")

        assert result is None

    def test_get_by_id_returns_none_on_error(
        self, repository: SQLAlchemyTaskRepository, mock_session: MagicMock
    ) -> None:
        """Test get_by_id returns None on database error."""
        mock_session.query.side_effect = SQLAlchemyError("Database error")

        result = repository.get_by_id("test-123")

        assert result is None

    @patch(
        "app.infrastructure.database.repositories.sqlalchemy_task_repository.to_domain"
    )
    def test_get_all_returns_all_tasks(
        self,
        mock_to_domain: Mock,
        repository: SQLAlchemyTaskRepository,
        mock_session: MagicMock,
    ) -> None:
        """Test get_all returns all tasks."""
        orm_task1 = MagicMock(spec=ORMTask)
        orm_task2 = MagicMock(spec=ORMTask)
        domain_task1 = TaskFactory(uuid="task-1")
        domain_task2 = TaskFactory(uuid="task-2")

        mock_session.query.return_value.all.return_value = [orm_task1, orm_task2]
        mock_to_domain.side_effect = [domain_task1, domain_task2]

        result = repository.get_all()

        assert len(result) == 2
        assert domain_task1 in result
        assert domain_task2 in result

    def test_get_all_returns_empty_list_when_no_tasks(
        self, repository: SQLAlchemyTaskRepository, mock_session: MagicMock
    ) -> None:
        """Test get_all returns empty list when no tasks exist."""
        mock_session.query.return_value.all.return_value = []

        result = repository.get_all()

        assert result == []

    @patch(
        "app.infrastructure.database.repositories.sqlalchemy_task_repository.to_domain"
    )
    def test_update_updates_task_successfully(
        self,
        mock_to_domain: Mock,
        repository: SQLAlchemyTaskRepository,
        mock_session: MagicMock,
    ) -> None:
        """Test updating a task successfully."""
        orm_task = MagicMock(spec=ORMTask)
        mock_session.query.return_value.filter.return_value.first.return_value = (
            orm_task
        )

        update_data = {
            "status": "completed",
            "result": {"text": "updated"},
            "duration": 15.5,
        }

        repository.update("test-123", update_data)

        # Verify update occurred
        assert orm_task.status == "completed"
        assert orm_task.result == {"text": "updated"}
        assert orm_task.duration == 15.5
        mock_session.commit.assert_called_once()

    def test_update_returns_none_when_task_not_found(
        self, repository: SQLAlchemyTaskRepository, mock_session: MagicMock
    ) -> None:
        """Test update raises ValueError when task doesn't exist."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="Task not found"):
            repository.update("non-existent", {"status": "completed"})

        mock_session.commit.assert_not_called()

    def test_delete_removes_task_successfully(
        self, repository: SQLAlchemyTaskRepository, mock_session: MagicMock
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
        self, repository: SQLAlchemyTaskRepository, mock_session: MagicMock
    ) -> None:
        """Test delete returns False when task doesn't exist."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = repository.delete("non-existent")

        assert result is False
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()
