"""Tests for TaskExecutor."""

from unittest.mock import Mock

import pytest

from app.domain.entities.background_task import BackgroundTask, TaskStatus
from app.infrastructure.tasks.task_executor import TaskExecutor
from app.infrastructure.tasks.task_registry import TaskRegistry


class TestTaskExecutor:
    """Test suite for TaskExecutor."""

    def test_execute_successful_task(self) -> None:
        """Test executing a task successfully."""
        # Setup
        registry = TaskRegistry()
        mock_repository = Mock()
        mock_repository.get_by_id.return_value = Mock(status="processing")

        def test_handler(value: int) -> dict[str, int]:
            return {"result": value * 2}

        registry.register("test_task", test_handler)

        executor = TaskExecutor(registry, mock_repository)

        task = BackgroundTask(
            task_id="test-123",
            task_type="test_task",
            parameters={"value": 5},
        )

        # Execute
        result = executor.execute(task)

        # Assert
        assert result == {"result": 10}
        assert mock_repository.update.called

    def test_execute_task_not_found(self) -> None:
        """Test executing task with unregistered handler."""
        # Setup
        registry = TaskRegistry()
        mock_repository = Mock()
        mock_repository.get_by_id.return_value = Mock(status="processing")

        executor = TaskExecutor(registry, mock_repository)

        task = BackgroundTask(
            task_id="test-456",
            task_type="nonexistent_task",
            parameters={},
        )

        # Execute & Assert
        with pytest.raises(ValueError, match="No handler registered"):
            executor.execute(task)

    def test_execute_task_with_failure(self) -> None:
        """Test executing a task that fails."""
        # Setup
        registry = TaskRegistry()
        mock_repository = Mock()
        mock_repository.get_by_id.return_value = Mock(status="processing")

        def failing_handler() -> None:
            raise RuntimeError("Task failed")

        registry.register("failing_task", failing_handler)

        executor = TaskExecutor(registry, mock_repository)

        task = BackgroundTask(
            task_id="test-789",
            task_type="failing_task",
            parameters={},
            max_retries=0,  # No retries
        )

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Task failed"):
            executor.execute(task)

        # Check that task was marked as failed
        update_calls = [call for call in mock_repository.update.call_args_list]
        assert any(
            "status" in call[1]["update_data"]
            and call[1]["update_data"]["status"] == TaskStatus.FAILED.value
            for call in update_calls
        )

    def test_execute_cancelled_task(self) -> None:
        """Test executing a task that was cancelled."""
        # Setup
        registry = TaskRegistry()
        mock_repository = Mock()

        # Mock task as cancelled
        cancelled_task_mock = Mock(status=TaskStatus.CANCELLED.value)
        mock_repository.get_by_id.return_value = cancelled_task_mock

        def test_handler() -> dict[str, str]:
            return {"result": "success"}

        registry.register("test_task", test_handler)

        executor = TaskExecutor(registry, mock_repository)

        task = BackgroundTask(
            task_id="test-cancelled",
            task_type="test_task",
            parameters={},
        )

        # Execute
        result = executor.execute(task)

        # Assert task was not executed
        assert result is None

    def test_update_task_db(self) -> None:
        """Test _update_task_db helper method."""
        # Setup
        registry = TaskRegistry()
        mock_repository = Mock()

        executor = TaskExecutor(registry, mock_repository)

        task = BackgroundTask(
            task_id="test-update",
            task_type="test",
            parameters={},
            status=TaskStatus.PROCESSING,
            retry_count=1,
            error_message="Test error",
        )

        # Execute
        executor._update_task_db(task)

        # Assert
        mock_repository.update.assert_called_once()
        call_args = mock_repository.update.call_args
        assert call_args[1]["identifier"] == "test-update"
        assert call_args[1]["update_data"]["status"] == TaskStatus.PROCESSING.value
        assert call_args[1]["update_data"]["retry_count"] == 1
