"""Unit tests for TaskManagementService."""

from unittest.mock import MagicMock

import pytest

from app.domain.entities.task import Task
from app.services.task_management_service import TaskManagementService


class TestTaskManagementService:
    """Test suite for TaskManagementService."""

    @pytest.fixture
    def mock_repository(self) -> MagicMock:
        """Create a mock repository for testing."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_repository: MagicMock) -> TaskManagementService:
        """Create a TaskManagementService instance with mock repository."""
        return TaskManagementService(mock_repository)

    @pytest.fixture
    def sample_task(self) -> Task:
        """Create a sample task for testing."""
        return Task(
            uuid="test-uuid-123",
            status="processing",
            task_type="transcription",
            file_name="test.mp3",
            language="en",
        )

    def test_create_task(
        self,
        service: TaskManagementService,
        mock_repository: MagicMock,
        sample_task: Task,
    ) -> None:
        """Test creating a task."""
        mock_repository.add.return_value = "test-uuid-123"

        result = service.create_task(sample_task)

        assert result == "test-uuid-123"
        mock_repository.add.assert_called_once_with(sample_task)

    def test_get_task_found(
        self,
        service: TaskManagementService,
        mock_repository: MagicMock,
        sample_task: Task,
    ) -> None:
        """Test getting a task that exists."""
        mock_repository.get_by_id.return_value = sample_task

        result = service.get_task("test-uuid-123")

        assert result == sample_task
        mock_repository.get_by_id.assert_called_once_with("test-uuid-123")

    def test_get_task_not_found(
        self, service: TaskManagementService, mock_repository: MagicMock
    ) -> None:
        """Test getting a task that doesn't exist."""
        mock_repository.get_by_id.return_value = None

        result = service.get_task("non-existent-uuid")

        assert result is None
        mock_repository.get_by_id.assert_called_once_with("non-existent-uuid")

    def test_get_all_tasks(
        self,
        service: TaskManagementService,
        mock_repository: MagicMock,
        sample_task: Task,
    ) -> None:
        """Test getting all tasks."""
        tasks = [sample_task, sample_task]
        mock_repository.get_all.return_value = tasks

        result = service.get_all_tasks()

        assert result == tasks
        assert len(result) == 2
        mock_repository.get_all.assert_called_once()

    def test_get_all_tasks_empty(
        self, service: TaskManagementService, mock_repository: MagicMock
    ) -> None:
        """Test getting all tasks when none exist."""
        mock_repository.get_all.return_value = []

        result = service.get_all_tasks()

        assert result == []
        mock_repository.get_all.assert_called_once()

    def test_delete_task_success(
        self, service: TaskManagementService, mock_repository: MagicMock
    ) -> None:
        """Test deleting a task successfully."""
        mock_repository.delete.return_value = True

        result = service.delete_task("test-uuid-123")

        assert result is True
        mock_repository.delete.assert_called_once_with("test-uuid-123")

    def test_delete_task_not_found(
        self, service: TaskManagementService, mock_repository: MagicMock
    ) -> None:
        """Test deleting a task that doesn't exist."""
        mock_repository.delete.return_value = False

        result = service.delete_task("non-existent-uuid")

        assert result is False
        mock_repository.delete.assert_called_once_with("non-existent-uuid")

    def test_update_task_status(
        self, service: TaskManagementService, mock_repository: MagicMock
    ) -> None:
        """Test updating task status."""
        update_data = {"status": "completed", "result": {"text": "transcription"}}

        service.update_task_status("test-uuid-123", update_data)

        mock_repository.update.assert_called_once_with("test-uuid-123", update_data)

    def test_update_task_status_with_error(
        self, service: TaskManagementService, mock_repository: MagicMock
    ) -> None:
        """Test updating task with error information."""
        update_data = {"status": "failed", "error": "Test error message"}

        service.update_task_status("test-uuid-123", update_data)

        mock_repository.update.assert_called_once_with("test-uuid-123", update_data)
