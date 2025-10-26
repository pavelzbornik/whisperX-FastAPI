"""Tests for BackgroundTask entity."""

import json
from datetime import datetime


from app.domain.entities.background_task import BackgroundTask, TaskResult, TaskStatus


class TestBackgroundTask:
    """Test suite for BackgroundTask entity."""

    def test_create_background_task(self) -> None:
        """Test creating a background task with required fields."""
        task = BackgroundTask(
            task_id="test-123",
            task_type="audio_processing",
            parameters={"file_path": "/tmp/audio.mp3"},
        )

        assert task.task_id == "test-123"
        assert task.task_type == "audio_processing"
        assert task.parameters == {"file_path": "/tmp/audio.mp3"}
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 0
        assert task.max_retries == 3
        assert task.error_message is None
        assert task.created_at is not None

    def test_background_task_with_custom_retries(self) -> None:
        """Test creating a task with custom retry count."""
        task = BackgroundTask(
            task_id="test-456",
            task_type="transcription",
            parameters={"audio": "data"},
            max_retries=5,
        )

        assert task.max_retries == 5

    def test_serialize_background_task(self) -> None:
        """Test serializing background task to JSON."""
        created_at = datetime(2023, 1, 1, 12, 0, 0)
        task = BackgroundTask(
            task_id="test-789",
            task_type="diarization",
            parameters={"device": "cuda"},
            created_at=created_at,
        )

        json_str = task.serialize()
        data = json.loads(json_str)

        assert data["task_id"] == "test-789"
        assert data["task_type"] == "diarization"
        assert data["parameters"] == {"device": "cuda"}
        assert data["status"] == "pending"
        assert data["created_at"] == created_at.isoformat()

    def test_deserialize_background_task(self) -> None:
        """Test deserializing background task from JSON."""
        json_data = {
            "task_id": "test-abc",
            "task_type": "alignment",
            "parameters": {"language": "en"},
            "status": "processing",
            "retry_count": 1,
            "max_retries": 3,
            "error_message": "Test error",
            "created_at": "2023-01-01T12:00:00",
            "started_at": "2023-01-01T12:01:00",
            "completed_at": None,
        }

        json_str = json.dumps(json_data)
        task = BackgroundTask.deserialize(json_str)

        assert task.task_id == "test-abc"
        assert task.task_type == "alignment"
        assert task.parameters == {"language": "en"}
        assert task.status == TaskStatus.PROCESSING
        assert task.retry_count == 1
        assert task.error_message == "Test error"
        assert task.created_at == datetime.fromisoformat("2023-01-01T12:00:00")
        assert task.started_at == datetime.fromisoformat("2023-01-01T12:01:00")
        assert task.completed_at is None

    def test_round_trip_serialization(self) -> None:
        """Test serializing and deserializing produces same task."""
        original = BackgroundTask(
            task_id="test-round-trip",
            task_type="test_task",
            parameters={"param1": "value1", "param2": 42},
            status=TaskStatus.COMPLETED,
            retry_count=2,
            max_retries=5,
        )

        json_str = original.serialize()
        restored = BackgroundTask.deserialize(json_str)

        assert restored.task_id == original.task_id
        assert restored.task_type == original.task_type
        assert restored.parameters == original.parameters
        assert restored.status == original.status
        assert restored.retry_count == original.retry_count
        assert restored.max_retries == original.max_retries


class TestTaskResult:
    """Test suite for TaskResult dataclass."""

    def test_create_task_result(self) -> None:
        """Test creating a task result."""
        result = TaskResult(
            task_id="test-result-123",
            status=TaskStatus.COMPLETED,
            result={"output": "success"},
            retry_count=0,
            duration_seconds=10.5,
        )

        assert result.task_id == "test-result-123"
        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"output": "success"}
        assert result.error is None
        assert result.retry_count == 0
        assert result.duration_seconds == 10.5

    def test_create_failed_task_result(self) -> None:
        """Test creating a failed task result."""
        result = TaskResult(
            task_id="test-failed",
            status=TaskStatus.FAILED,
            error="Test error message",
            retry_count=3,
        )

        assert result.task_id == "test-failed"
        assert result.status == TaskStatus.FAILED
        assert result.result is None
        assert result.error == "Test error message"
        assert result.retry_count == 3


class TestTaskStatus:
    """Test suite for TaskStatus enum."""

    def test_task_status_values(self) -> None:
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.QUEUED.value == "queued"
        assert TaskStatus.PROCESSING.value == "processing"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_task_status_from_string(self) -> None:
        """Test creating TaskStatus from string."""
        status = TaskStatus("processing")
        assert status == TaskStatus.PROCESSING
