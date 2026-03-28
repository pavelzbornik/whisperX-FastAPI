"""Unit tests for audio processing service."""

import threading
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.services.audio_processing_service import (
    process_audio_task,
    validate_language_code,
)


@pytest.mark.unit
class TestAudioProcessingService:
    """Unit tests for audio processing service functions."""

    def test_validate_language_code_with_valid_code(self) -> None:
        """Test validation passes for valid language code."""
        # Should not raise any exception
        validate_language_code("en")
        validate_language_code("es")
        validate_language_code("fr")

    def test_validate_language_code_with_invalid_code(self) -> None:
        """Test validation raises error for invalid language code."""
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Invalid language code"):
            validate_language_code("invalid")

        with pytest.raises(ValidationError, match="Invalid language code"):
            validate_language_code("xyz")

    @patch("app.services.audio_processing_service.SyncSQLAlchemyTaskRepository")
    @patch("app.services.audio_processing_service.SyncSessionLocal")
    def test_process_audio_task_success(
        self, mock_session_local: Mock, mock_repository_class: Mock
    ) -> None:
        """Test processing audio task successfully."""
        # Setup mocks
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_repository = MagicMock()
        mock_repository_class.return_value = mock_repository

        # Create a mock processor that returns a result
        mock_processor = Mock(return_value={"segments": [{"text": "hello"}]})

        # Execute
        process_audio_task(
            audio_processor=mock_processor,
            identifier="test-123",
            task_type="transcription",
        )

        # Verify: first call transitions to processing, second marks completed
        assert mock_repository.update.call_count == 2

        processing_call = mock_repository.update.call_args_list[0]
        assert processing_call[1]["identifier"] == "test-123"
        assert processing_call[1]["update_data"]["status"] == "processing"

        completed_call = mock_repository.update.call_args_list[1]
        assert completed_call[1]["identifier"] == "test-123"
        assert completed_call[1]["update_data"]["status"] == "completed"
        assert completed_call[1]["update_data"]["result"] == {
            "segments": [{"text": "hello"}]
        }

        mock_processor.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("app.services.audio_processing_service.SyncSQLAlchemyTaskRepository")
    @patch("app.services.audio_processing_service.SyncSessionLocal")
    def test_process_audio_task_handles_diarization_result(
        self, mock_session_local: Mock, mock_repository_class: Mock
    ) -> None:
        """Test processing diarization task converts DataFrame to dict."""
        import pandas as pd

        # Setup mocks
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_repository = MagicMock()
        mock_repository_class.return_value = mock_repository

        # Create a mock diarization result (DataFrame)
        df = pd.DataFrame(
            {
                "start": [0.0, 1.0],
                "end": [1.0, 2.0],
                "speaker": ["SPEAKER_00", "SPEAKER_01"],
                "segment": [None, None],
            }
        )
        mock_processor = Mock(return_value=df)

        # Execute
        process_audio_task(
            audio_processor=mock_processor,
            identifier="test-456",
            task_type="diarization",
        )

        # Verify: second update call has the completed result
        assert mock_repository.update.call_count == 2
        completed_call = mock_repository.update.call_args_list[1]
        result = completed_call[1]["update_data"]["result"]
        # Should be a list of dicts, not a DataFrame
        assert isinstance(result, list)
        assert len(result) == 2
        assert "segment" not in result[0]  # segment column should be dropped

    @patch("app.services.audio_processing_service.SyncSQLAlchemyTaskRepository")
    @patch("app.services.audio_processing_service.SyncSessionLocal")
    def test_process_audio_task_handles_error(
        self, mock_session_local: Mock, mock_repository_class: Mock
    ) -> None:
        """Test processing audio task handles errors gracefully."""
        # Setup mocks
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_repository = MagicMock()
        mock_repository_class.return_value = mock_repository

        # Create a mock processor that raises an error
        mock_processor = Mock(side_effect=ValueError("Processing error"))

        # Execute - should not raise, but mark task as failed
        process_audio_task(
            audio_processor=mock_processor,
            identifier="test-789",
            task_type="transcription",
        )

        # Verify: first call transitions to processing, second marks failed
        assert mock_repository.update.call_count == 2

        processing_call = mock_repository.update.call_args_list[0]
        assert processing_call[1]["update_data"]["status"] == "processing"

        failed_call = mock_repository.update.call_args_list[1]
        assert failed_call[1]["identifier"] == "test-789"
        assert failed_call[1]["update_data"]["status"] == "failed"
        assert "error" in failed_call[1]["update_data"]
        mock_session.close.assert_called_once()

    @patch("app.services.audio_processing_service.SyncSQLAlchemyTaskRepository")
    @patch("app.services.audio_processing_service.SyncSessionLocal")
    def test_process_audio_task_records_timing(
        self, mock_session_local: Mock, mock_repository_class: Mock
    ) -> None:
        """Test processing records start time, end time, and duration."""
        # Setup mocks
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_repository = MagicMock()
        mock_repository_class.return_value = mock_repository

        mock_processor = Mock(return_value={"result": "data"})

        # Execute
        process_audio_task(
            audio_processor=mock_processor,
            identifier="test-timing",
            task_type="alignment",
        )

        # Verify timing was recorded in the completed update call
        completed_call = mock_repository.update.call_args_list[1]
        update_data = completed_call[1]["update_data"]
        assert "start_time" in update_data
        assert "end_time" in update_data
        assert "duration" in update_data
        assert isinstance(update_data["duration"], float)
        assert update_data["duration"] >= 0


@pytest.mark.unit
class TestGpuSemaphoreIntegration:
    """Tests for GPU semaphore integration in audio processing service."""

    @patch("app.services.audio_processing_service.SyncSQLAlchemyTaskRepository")
    @patch("app.services.audio_processing_service.SyncSessionLocal")
    @patch("app.core.gpu_semaphore.get_settings")
    def test_gpu_semaphore_acquired_and_released(
        self,
        mock_get_settings: Mock,
        mock_session_local: Mock,
        mock_repository_class: Mock,
    ) -> None:
        """Test GPU semaphore is acquired and released for GPU tasks."""
        from app.core.gpu_semaphore import get_gpu_semaphore

        get_gpu_semaphore.cache_clear()
        mock_get_settings.return_value = MagicMock(MAX_CONCURRENT_GPU_TASKS=1)

        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_repository = MagicMock()
        mock_repository_class.return_value = mock_repository

        mock_processor = Mock(return_value={"text": "hello"})

        process_audio_task(
            audio_processor=mock_processor,
            identifier="test-gpu",
            task_type="transcription",
            use_gpu_semaphore=True,
        )

        # Semaphore should be available again (was released)
        sem = get_gpu_semaphore()
        assert sem.acquire(blocking=False)
        sem.release()

        mock_processor.assert_called_once()
        get_gpu_semaphore.cache_clear()

    @patch("app.services.audio_processing_service.SyncSQLAlchemyTaskRepository")
    @patch("app.services.audio_processing_service.SyncSessionLocal")
    @patch("app.core.gpu_semaphore.get_settings")
    def test_gpu_semaphore_released_on_error(
        self,
        mock_get_settings: Mock,
        mock_session_local: Mock,
        mock_repository_class: Mock,
    ) -> None:
        """Test GPU semaphore is released even when processor raises."""
        from app.core.gpu_semaphore import get_gpu_semaphore

        get_gpu_semaphore.cache_clear()
        mock_get_settings.return_value = MagicMock(MAX_CONCURRENT_GPU_TASKS=1)

        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_repository = MagicMock()
        mock_repository_class.return_value = mock_repository

        mock_processor = Mock(side_effect=RuntimeError("GPU error"))

        process_audio_task(
            audio_processor=mock_processor,
            identifier="test-gpu-error",
            task_type="transcription",
            use_gpu_semaphore=True,
        )

        # Semaphore should be available again despite the error
        sem = get_gpu_semaphore()
        assert sem.acquire(blocking=False)
        sem.release()
        get_gpu_semaphore.cache_clear()

    @patch("app.services.audio_processing_service.SyncSQLAlchemyTaskRepository")
    @patch("app.services.audio_processing_service.SyncSessionLocal")
    @patch("app.core.gpu_semaphore.get_settings")
    def test_gpu_semaphore_not_used_for_cpu_tasks(
        self,
        mock_get_settings: Mock,
        mock_session_local: Mock,
        mock_repository_class: Mock,
    ) -> None:
        """Test GPU semaphore is not acquired when use_gpu_semaphore=False."""
        from app.core.gpu_semaphore import get_gpu_semaphore

        get_gpu_semaphore.cache_clear()
        mock_get_settings.return_value = MagicMock(MAX_CONCURRENT_GPU_TASKS=1)

        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_repository = MagicMock()
        mock_repository_class.return_value = mock_repository

        mock_processor = Mock(return_value={"result": "data"})

        # Default use_gpu_semaphore=False — semaphore should not be acquired
        process_audio_task(
            audio_processor=mock_processor,
            identifier="test-cpu",
            task_type="combine_transcript&diarization",
        )

        # Semaphore should still be fully available (never acquired)
        sem = get_gpu_semaphore()
        assert sem.acquire(blocking=False)
        sem.release()
        get_gpu_semaphore.cache_clear()

    @patch("app.services.audio_processing_service.SyncSQLAlchemyTaskRepository")
    @patch("app.services.audio_processing_service.SyncSessionLocal")
    @patch("app.core.gpu_semaphore.get_settings")
    def test_gpu_semaphore_blocks_concurrent_tasks(
        self,
        mock_get_settings: Mock,
        mock_session_local: Mock,
        mock_repository_class: Mock,
    ) -> None:
        """Test GPU semaphore blocks when all slots are taken."""
        from app.core.gpu_semaphore import get_gpu_semaphore

        get_gpu_semaphore.cache_clear()
        mock_get_settings.return_value = MagicMock(MAX_CONCURRENT_GPU_TASKS=1)

        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_repository = MagicMock()
        mock_repository_class.return_value = mock_repository

        barrier = threading.Event()
        task2_started = threading.Event()

        def slow_processor() -> dict[str, str]:
            barrier.wait(timeout=5)
            return {"text": "done"}

        def fast_processor() -> dict[str, str]:
            task2_started.set()
            return {"text": "done"}

        # Start first task that holds the semaphore
        t1 = threading.Thread(
            target=process_audio_task,
            kwargs={
                "audio_processor": slow_processor,
                "identifier": "task-1",
                "task_type": "transcription",
                "use_gpu_semaphore": True,
            },
        )
        t1.start()

        # Give t1 time to acquire the semaphore
        import time

        time.sleep(0.1)

        # Start second task — should be blocked
        t2 = threading.Thread(
            target=process_audio_task,
            kwargs={
                "audio_processor": fast_processor,
                "identifier": "task-2",
                "task_type": "transcription",
                "use_gpu_semaphore": True,
            },
        )
        t2.start()

        # Task 2 should NOT have started yet
        assert not task2_started.wait(timeout=0.3)

        # Release task 1
        barrier.set()
        t1.join(timeout=5)

        # Now task 2 should complete
        t2.join(timeout=5)
        assert task2_started.is_set()

        get_gpu_semaphore.cache_clear()
