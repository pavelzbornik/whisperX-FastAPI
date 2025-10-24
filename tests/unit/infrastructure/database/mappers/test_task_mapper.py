"""Unit tests for database task mapper."""

from datetime import datetime

import pytest

from app.domain.entities.task import Task as DomainTask
from app.infrastructure.database.mappers.task_mapper import to_domain, to_orm
from app.infrastructure.database.models import Task as ORMTask
from tests.factories import TaskFactory


@pytest.mark.unit
class TestTaskMapper:
    """Unit tests for task mapper functions."""

    def test_to_orm_converts_domain_to_orm(self) -> None:
        """Test converting domain task to ORM task."""
        domain_task = TaskFactory(
            uuid="test-123",
            status="processing",
            task_type="transcription",
            file_name="test.mp3",
            language="en",
        )

        orm_task = to_orm(domain_task)

        assert isinstance(orm_task, ORMTask)
        assert orm_task.uuid == "test-123"
        assert orm_task.status == "processing"
        assert orm_task.task_type == "transcription"
        assert orm_task.file_name == "test.mp3"
        assert orm_task.language == "en"

    def test_to_orm_with_all_fields(self) -> None:
        """Test converting domain task with all fields populated."""
        now = datetime.utcnow()
        domain_task = TaskFactory(
            uuid="test-123",
            status="completed",
            task_type="transcription",
            result={"segments": [{"text": "hello"}]},
            file_name="test.mp3",
            url="https://example.com/test.mp3",
            audio_duration=120.5,
            language="en",
            task_params={"model": "tiny"},
            duration=10.5,
            start_time=now,
            end_time=now,
            error=None,
        )

        orm_task = to_orm(domain_task)

        assert orm_task.result == {"segments": [{"text": "hello"}]}
        assert orm_task.url == "https://example.com/test.mp3"
        assert orm_task.audio_duration == pytest.approx(120.5)
        assert orm_task.task_params == {"model": "tiny"}
        assert orm_task.duration == pytest.approx(10.5)
        assert orm_task.start_time == now
        assert orm_task.end_time == now

    def test_to_domain_converts_orm_to_domain(self) -> None:
        """Test converting ORM task to domain task."""
        orm_task = ORMTask(
            uuid="test-456",
            status="pending",
            task_type="alignment",
            file_name="audio.wav",
            language="es",
        )

        domain_task = to_domain(orm_task)

        assert isinstance(domain_task, DomainTask)
        assert domain_task.uuid == "test-456"
        assert domain_task.status == "pending"
        assert domain_task.task_type == "alignment"
        assert domain_task.file_name == "audio.wav"
        assert domain_task.language == "es"

    def test_to_domain_with_all_fields(self) -> None:
        """Test converting ORM task with all fields populated."""
        now = datetime.utcnow()
        orm_task = ORMTask(
            uuid="test-456",
            status="failed",
            task_type="diarization",
            result=None,
            file_name="audio.wav",
            url="https://example.com/audio.wav",
            audio_duration=300.0,
            language="fr",
            task_params={"speakers": 2},
            duration=None,
            start_time=now,
            end_time=now,
            error="Processing failed",
            created_at=now,
            updated_at=now,
        )

        domain_task = to_domain(orm_task)

        assert domain_task.error == "Processing failed"
        assert domain_task.url == "https://example.com/audio.wav"
        assert domain_task.audio_duration == pytest.approx(300.0)
        assert domain_task.task_params == {"speakers": 2}
        assert domain_task.start_time == now
        assert domain_task.end_time == now
        assert domain_task.created_at == now
        assert domain_task.updated_at == now

    def test_round_trip_conversion(self) -> None:
        """Test converting domain -> ORM -> domain preserves data."""
        original_task = TaskFactory(
            uuid="round-trip-123",
            status="completed",
            task_type="transcription",
            result={"text": "test"},
            file_name="test.mp3",
            language="en",
        )

        # Convert to ORM and back
        orm_task = to_orm(original_task)
        converted_task = to_domain(orm_task)

        # Verify all fields match
        assert converted_task.uuid == original_task.uuid
        assert converted_task.status == original_task.status
        assert converted_task.task_type == original_task.task_type
        assert converted_task.result == original_task.result
        assert converted_task.file_name == original_task.file_name
        assert converted_task.language == original_task.language

    def test_round_trip_with_none_values(self) -> None:
        """Test round trip conversion preserves None values."""
        original_task = TaskFactory(
            uuid="none-test-123",
            status="pending",
            task_type="transcription",
            result=None,
            url=None,
            duration=None,
            start_time=None,
            end_time=None,
            error=None,
        )

        # Convert to ORM and back
        orm_task = to_orm(original_task)
        converted_task = to_domain(orm_task)

        # Verify None values are preserved
        assert converted_task.result is None
        assert converted_task.url is None
        assert converted_task.duration is None
        assert converted_task.start_time is None
        assert converted_task.end_time is None
        assert converted_task.error is None
