"""Unit tests for task API mapper.

Tests the conversion between API DTOs and domain entities.
"""

from datetime import datetime

import pytest

from app.api.mappers.task_mapper import TaskMapper
from app.api.schemas.task_schemas import (
    CreateTaskRequest,
    TaskResponse,
    TaskSummaryResponse,
)
from app.domain.entities.task import Task


class TestTaskMapper:
    """Test suite for TaskMapper."""

    def test_to_domain_with_uuid(self) -> None:
        """Test converting CreateTaskRequest DTO to domain Task entity with provided UUID."""
        dto = CreateTaskRequest(
            task_type="transcription",
            file_name="test.mp3",
            url=None,
            audio_duration=120.5,
            language="en",
            task_params={"model": "tiny"},
        )

        task_uuid = "test-uuid-123"
        domain_task = TaskMapper.to_domain(dto, uuid=task_uuid)

        assert domain_task.uuid == task_uuid
        assert domain_task.status == "processing"
        assert domain_task.task_type == "transcription"
        assert domain_task.file_name == "test.mp3"
        assert domain_task.url is None
        assert domain_task.audio_duration == pytest.approx(120.5)
        assert domain_task.language == "en"
        assert domain_task.task_params == {"model": "tiny"}

    def test_to_domain_without_uuid(self) -> None:
        """Test converting CreateTaskRequest DTO to domain Task entity with auto-generated UUID."""
        dto = CreateTaskRequest(
            task_type="diarization",
            file_name="audio.wav",
            url=None,
            audio_duration=60.0,
            language="fr",
            task_params=None,
        )

        domain_task = TaskMapper.to_domain(dto)

        assert domain_task.uuid is not None
        assert len(domain_task.uuid) > 0
        assert domain_task.status == "processing"
        assert domain_task.task_type == "diarization"

    def test_to_response(self) -> None:
        """Test converting domain Task entity to TaskResponse DTO."""
        now = datetime.utcnow()
        domain_task = Task(
            uuid="task-456",
            status="completed",
            task_type="transcription",
            file_name="audio.mp3",
            url="http://example.com/audio.mp3",
            audio_duration=180.0,
            language="es",
            task_params={"beam_size": 5},
            result={"text": "transcribed text"},
            error=None,
            duration=15.5,
            start_time=now,
            end_time=now,
            created_at=now,
            updated_at=now,
        )

        response = TaskMapper.to_response(domain_task)

        assert isinstance(response, TaskResponse)
        assert response.identifier == "task-456"
        assert response.status == "completed"
        assert response.task_type == "transcription"
        assert response.file_name == "audio.mp3"
        assert response.url == "http://example.com/audio.mp3"
        assert response.audio_duration == pytest.approx(180.0)
        assert response.language == "es"
        assert response.task_params == {"beam_size": 5}
        assert response.result == {"text": "transcribed text"}
        assert response.error is None
        assert response.duration == pytest.approx(15.5)
        assert response.start_time == now
        assert response.end_time == now
        assert response.created_at == now
        assert response.updated_at == now

    def test_to_summary(self) -> None:
        """Test converting domain Task entity to TaskSummaryResponse DTO."""
        now = datetime.utcnow()
        domain_task = Task(
            uuid="task-789",
            status="failed",
            task_type="alignment",
            file_name="speech.wav",
            url=None,
            audio_duration=90.0,
            language="de",
            task_params=None,
            result=None,
            error="Processing failed",
            duration=5.0,
            start_time=now,
            end_time=now,
            created_at=now,
            updated_at=now,
        )

        summary = TaskMapper.to_summary(domain_task)

        assert isinstance(summary, TaskSummaryResponse)
        assert summary.identifier == "task-789"
        assert summary.status == "failed"
        assert summary.task_type == "alignment"
        assert summary.file_name == "speech.wav"
        assert summary.url is None
        assert summary.audio_duration == pytest.approx(90.0)
        assert summary.language == "de"
        assert summary.error == "Processing failed"
        assert summary.duration == pytest.approx(5.0)
        assert summary.start_time == now
        assert summary.end_time == now

    def test_round_trip_conversion(self) -> None:
        """Test that converting DTO -> domain -> DTO preserves data."""
        original_dto = CreateTaskRequest(
            task_type="full_process",
            file_name="complete.mp3",
            url="http://example.com/complete.mp3",
            audio_duration=300.0,
            language="ja",
            task_params={"model": "medium", "beam_size": 10},
        )

        # Convert to domain
        domain_task = TaskMapper.to_domain(original_dto, uuid="round-trip-test")

        # Convert back to response DTO
        response_dto = TaskMapper.to_response(domain_task)

        # Verify key fields match
        assert response_dto.identifier == "round-trip-test"
        assert response_dto.task_type == original_dto.task_type
        assert response_dto.file_name == original_dto.file_name
        assert response_dto.url == original_dto.url
        assert response_dto.audio_duration == original_dto.audio_duration
        assert response_dto.language == original_dto.language
        assert response_dto.task_params == original_dto.task_params

    def test_to_summary_excludes_result(self) -> None:
        """Test that TaskSummaryResponse doesn't include result data."""
        domain_task = Task(
            uuid="task-summary-test",
            status="completed",
            task_type="transcription",
            file_name="test.mp3",
            url=None,
            audio_duration=60.0,
            language="en",
            task_params=None,
            result={"segments": [{"text": "large result data"}]},  # Large result
            error=None,
            duration=10.0,
        )

        summary = TaskMapper.to_summary(domain_task)

        # Summary should not have a result field
        assert not hasattr(summary, "result")
        # But should have other key fields
        assert summary.identifier == "task-summary-test"
        assert summary.status == "completed"
