"""Integration tests for task lifecycle with real database."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.infrastructure.database.repositories.sqlalchemy_task_repository import (
    SQLAlchemyTaskRepository,
)
from tests.factories import TaskFactory

# Fixtures are imported via conftest.py, no need to import them here


@pytest.mark.integration
class TestTaskLifecycle:
    """Integration tests for complete task lifecycle with real database."""

    def test_create_and_retrieve_task(self, db_session: Session) -> None:
        """Test creating a task and retrieving it from database."""
        repository = SQLAlchemyTaskRepository(db_session)

        # Create task
        task = TaskFactory(
            uuid="integration-test-123",
            status="pending",
            task_type="transcription",
            file_name="audio.mp3",
            language="en",
        )
        task_id = repository.add(task)

        # Retrieve task
        retrieved = repository.get_by_id(task_id)

        assert retrieved is not None
        assert retrieved.uuid == "integration-test-123"
        assert retrieved.status == "pending"
        assert retrieved.task_type == "transcription"
        assert retrieved.file_name == "audio.mp3"
        assert retrieved.language == "en"

    def test_update_task_status(self, db_session: Session) -> None:
        """Test updating task status persists to database."""
        repository = SQLAlchemyTaskRepository(db_session)

        # Create and save task
        task = TaskFactory(uuid="update-test-456", status="pending")
        task_id = repository.add(task)

        # Update task
        repository.update(
            task_id,
            {
                "status": "completed",
                "result": {"segments": [{"text": "hello"}]},
                "duration": 10.5,
            },
        )

        # Verify persistence by retrieving again
        retrieved = repository.get_by_id(task_id)
        assert retrieved is not None
        assert retrieved.status == "completed"
        assert retrieved.result == {"segments": [{"text": "hello"}]}
        assert retrieved.duration == pytest.approx(10.5)

    def test_complete_task_lifecycle(self, db_session: Session) -> None:
        """Test complete task lifecycle from creation to completion."""
        repository = SQLAlchemyTaskRepository(db_session)

        # 1. Create pending task
        task = TaskFactory(
            uuid="lifecycle-test-789",
            status="pending",
            task_type="transcription",
            file_name="test.mp3",
        )
        task_id = repository.add(task)
        assert task_id == "lifecycle-test-789"

        # 2. Mark as processing
        start_time = datetime.now(timezone.utc)
        repository.update(task_id, {"status": "processing", "start_time": start_time})
        processing_task = repository.get_by_id(task_id)
        assert processing_task is not None
        assert processing_task.status == "processing"
        assert processing_task.start_time is not None

        # 3. Complete the task
        end_time = datetime.now(timezone.utc)
        repository.update(
            task_id,
            {
                "status": "completed",
                "result": {"text": "transcription result"},
                "duration": 15.5,
                "end_time": end_time,
            },
        )
        completed_task = repository.get_by_id(task_id)
        assert completed_task is not None
        assert completed_task.status == "completed"
        assert completed_task.result is not None
        assert completed_task.duration == pytest.approx(15.5)
        assert completed_task.end_time is not None

    def test_fail_task_lifecycle(self, db_session: Session) -> None:
        """Test task lifecycle ending in failure."""
        repository = SQLAlchemyTaskRepository(db_session)

        # 1. Create and start processing
        task = TaskFactory(uuid="fail-test-001", status="processing")
        task_id = repository.add(task)

        # 2. Mark as failed
        repository.update(
            task_id,
            {
                "status": "failed",
                "error": "Processing timeout",
                "end_time": datetime.now(timezone.utc),
            },
        )

        failed_task = repository.get_by_id(task_id)
        assert failed_task is not None
        assert failed_task.status == "failed"
        assert failed_task.error == "Processing timeout"
        assert failed_task.end_time is not None

    def test_get_all_tasks(self, db_session: Session) -> None:
        """Test retrieving all tasks from database."""
        repository = SQLAlchemyTaskRepository(db_session)

        # Create multiple tasks
        task1 = TaskFactory(uuid="all-test-001", status="pending")
        task2 = TaskFactory(uuid="all-test-002", status="processing")
        task3 = TaskFactory(uuid="all-test-003", status="completed")

        repository.add(task1)
        repository.add(task2)
        repository.add(task3)

        # Retrieve all tasks
        all_tasks = repository.get_all()

        assert len(all_tasks) == 3
        uuids = [t.uuid for t in all_tasks]
        assert "all-test-001" in uuids
        assert "all-test-002" in uuids
        assert "all-test-003" in uuids

    def test_delete_task(self, db_session: Session) -> None:
        """Test deleting a task from database."""
        repository = SQLAlchemyTaskRepository(db_session)

        # Create task
        task = TaskFactory(uuid="delete-test-999")
        task_id = repository.add(task)

        # Verify it exists
        assert repository.get_by_id(task_id) is not None

        # Delete task
        deleted = repository.delete(task_id)
        assert deleted is True

        # Verify it's gone
        assert repository.get_by_id(task_id) is None

    def test_update_nonexistent_task_returns_none(self, db_session: Session) -> None:
        """Test updating non-existent task raises ValueError."""
        repository = SQLAlchemyTaskRepository(db_session)

        with pytest.raises(ValueError, match="Task not found"):
            repository.update("non-existent-uuid", {"status": "completed"})

    def test_delete_nonexistent_task_returns_false(self, db_session: Session) -> None:
        """Test deleting non-existent task returns False."""
        repository = SQLAlchemyTaskRepository(db_session)

        result = repository.delete("non-existent-uuid")

        assert result is False

    def test_task_with_complex_result_data(self, db_session: Session) -> None:
        """Test task with complex nested result data."""
        repository = SQLAlchemyTaskRepository(db_session)

        complex_result = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Hello",
                    "words": [
                        {"word": "Hello", "start": 0.0, "end": 0.5},
                    ],
                },
                {
                    "start": 5.0,
                    "end": 10.0,
                    "text": "World",
                    "words": [
                        {"word": "World", "start": 5.0, "end": 5.5},
                    ],
                },
            ],
            "language": "en",
        }

        task = TaskFactory(
            uuid="complex-result-001",
            status="completed",
            result=complex_result,
        )
        task_id = repository.add(task)

        # Retrieve and verify complex data
        retrieved = repository.get_by_id(task_id)
        assert retrieved is not None
        assert retrieved.result == complex_result
        assert len(retrieved.result["segments"]) == 2
