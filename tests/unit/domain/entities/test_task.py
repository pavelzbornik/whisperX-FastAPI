"""Unit tests for Task domain entity."""

from datetime import datetime

import pytest

from app.domain.entities.task import Task
from tests.factories import TaskFactory


@pytest.mark.unit
class TestTaskEntity:
    """Unit tests for Task domain entity."""

    def test_create_task_with_required_fields(self) -> None:
        """Test creating a task with only required fields."""
        task = Task(
            uuid="test-123",
            status="pending",
            task_type="transcription",
        )

        assert task.uuid == "test-123"
        assert task.status == "pending"
        assert task.task_type == "transcription"
        assert task.result is None
        assert task.error is None

    def test_create_task_with_all_fields(self) -> None:
        """Test creating a task with all fields populated."""
        task = Task(
            uuid="test-123",
            status="processing",
            task_type="transcription",
            file_name="audio.mp3",
            url="https://example.com/audio.mp3",
            audio_duration=120.5,
            language="en",
            task_params={"model": "tiny"},
        )

        assert task.uuid == "test-123"
        assert task.status == "processing"
        assert task.file_name == "audio.mp3"
        assert task.url == "https://example.com/audio.mp3"
        assert task.audio_duration == 120.5
        assert task.language == "en"
        assert task.task_params == {"model": "tiny"}

    def test_mark_as_completed(self) -> None:
        """Test marking a task as completed updates status and result."""
        task = TaskFactory(status="processing")
        result = {"segments": [{"text": "hello world"}]}
        end_time = datetime.utcnow()

        task.mark_as_completed(result, duration=10.5, end_time=end_time)

        assert task.status == "completed"
        assert task.result == result
        assert task.duration == pytest.approx(10.5)
        assert task.end_time == end_time
        assert task.updated_at is not None

    def test_mark_as_failed(self) -> None:
        """Test marking a task as failed updates status and error."""
        task = TaskFactory(status="processing")
        error_message = "Processing failed due to timeout"

        task.mark_as_failed(error_message)

        assert task.status == "failed"
        assert task.error == error_message
        assert task.end_time is not None
        assert task.updated_at is not None

    def test_mark_as_processing(self) -> None:
        """Test marking a task as processing updates status and start time."""
        task = TaskFactory(status="pending")
        start_time = datetime.utcnow()

        task.mark_as_processing(start_time)

        assert task.status == "processing"
        assert task.start_time == start_time
        assert task.updated_at is not None

    def test_is_processing_returns_true_for_processing_task(self) -> None:
        """Test is_processing returns True for processing tasks."""
        task = TaskFactory(status="processing")
        assert task.is_processing() is True

    def test_is_processing_returns_false_for_non_processing_task(self) -> None:
        """Test is_processing returns False for non-processing tasks."""
        pending_task = TaskFactory(status="pending")
        completed_task = TaskFactory(status="completed")
        failed_task = TaskFactory(status="failed")

        assert pending_task.is_processing() is False
        assert completed_task.is_processing() is False
        assert failed_task.is_processing() is False

    def test_is_completed_returns_true_for_completed_task(self) -> None:
        """Test is_completed returns True for completed tasks."""
        task = TaskFactory(status="completed")
        assert task.is_completed() is True

    def test_is_completed_returns_false_for_non_completed_task(self) -> None:
        """Test is_completed returns False for non-completed tasks."""
        pending_task = TaskFactory(status="pending")
        processing_task = TaskFactory(status="processing")
        failed_task = TaskFactory(status="failed")

        assert pending_task.is_completed() is False
        assert processing_task.is_completed() is False
        assert failed_task.is_completed() is False

    def test_is_failed_returns_true_for_failed_task(self) -> None:
        """Test is_failed returns True for failed tasks."""
        task = TaskFactory(status="failed")
        assert task.is_failed() is True

    def test_is_failed_returns_false_for_non_failed_task(self) -> None:
        """Test is_failed returns False for non-failed tasks."""
        pending_task = TaskFactory(status="pending")
        processing_task = TaskFactory(status="processing")
        completed_task = TaskFactory(status="completed")

        assert pending_task.is_failed() is False
        assert processing_task.is_failed() is False
        assert completed_task.is_failed() is False

    def test_task_factory_creates_valid_task(self) -> None:
        """Test TaskFactory creates a valid task with defaults."""
        task = TaskFactory()

        assert task.uuid is not None
        assert task.status == "pending"
        assert task.task_type == "transcription"
        assert task.language == "en"

    def test_task_factory_processing_creates_processing_task(self) -> None:
        """Test TaskFactory.processing creates a task in processing state."""
        task = TaskFactory.processing()

        assert task.status == "processing"
        assert task.start_time is not None

    def test_task_factory_completed_creates_completed_task(self) -> None:
        """Test TaskFactory.completed creates a task in completed state."""
        task = TaskFactory.completed()

        assert task.status == "completed"
        assert task.result is not None
        assert task.duration is not None
        assert task.end_time is not None

    def test_task_factory_failed_creates_failed_task(self) -> None:
        """Test TaskFactory.failed creates a task in failed state."""
        task = TaskFactory.failed()

        assert task.status == "failed"
        assert task.error is not None
        assert task.end_time is not None

    def test_state_transitions(self) -> None:
        """Test complete lifecycle of task state transitions."""
        # Start with pending task
        task = TaskFactory(status="pending")
        assert task.status == "pending"
        assert not task.is_processing()
        assert not task.is_completed()
        assert not task.is_failed()

        # Move to processing
        task.mark_as_processing(datetime.utcnow())
        assert task.status == "processing"
        assert task.is_processing()
        assert not task.is_completed()
        assert not task.is_failed()

        # Complete the task
        task.mark_as_completed(
            {"result": "data"}, duration=5.5, end_time=datetime.utcnow()
        )
        assert task.status == "completed"
        assert not task.is_processing()
        assert task.is_completed()
        assert not task.is_failed()
        assert task.duration == pytest.approx(5.5)

    def test_state_transitions_to_failed(self) -> None:
        """Test task transition from processing to failed."""
        # Start with processing task
        task = TaskFactory(status="processing", start_time=datetime.utcnow())
        assert task.is_processing()

        # Fail the task
        task.mark_as_failed("Something went wrong")
        assert task.status == "failed"
        assert not task.is_processing()
        assert not task.is_completed()
        assert task.is_failed()
        assert task.error == "Something went wrong"
