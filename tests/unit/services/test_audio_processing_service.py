"""Unit tests for audio processing service."""

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

    @patch("app.services.audio_processing_service.SQLAlchemyTaskRepository")
    @patch("app.services.audio_processing_service.SessionLocal")
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

        # Verify
        mock_processor.assert_called_once()
        mock_repository.update.assert_called_once()
        update_call = mock_repository.update.call_args
        assert update_call[1]["identifier"] == "test-123"
        assert update_call[1]["update_data"]["status"] == "completed"
        assert update_call[1]["update_data"]["result"] == {
            "segments": [{"text": "hello"}]
        }
        mock_session.close.assert_called_once()

    @patch("app.services.audio_processing_service.SQLAlchemyTaskRepository")
    @patch("app.services.audio_processing_service.SessionLocal")
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

        # Verify
        mock_repository.update.assert_called_once()
        update_call = mock_repository.update.call_args
        result = update_call[1]["update_data"]["result"]
        # Should be a list of dicts, not a DataFrame
        assert isinstance(result, list)
        assert len(result) == 2
        assert "segment" not in result[0]  # segment column should be dropped

    @patch("app.services.audio_processing_service.SQLAlchemyTaskRepository")
    @patch("app.services.audio_processing_service.SessionLocal")
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

        # Verify task was marked as failed
        mock_repository.update.assert_called_once()
        update_call = mock_repository.update.call_args
        assert update_call[1]["identifier"] == "test-789"
        assert update_call[1]["update_data"]["status"] == "failed"
        assert "error" in update_call[1]["update_data"]
        mock_session.close.assert_called_once()

    @patch("app.services.audio_processing_service.SQLAlchemyTaskRepository")
    @patch("app.services.audio_processing_service.SessionLocal")
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

        # Verify timing was recorded
        update_call = mock_repository.update.call_args
        update_data = update_call[1]["update_data"]
        assert "start_time" in update_data
        assert "end_time" in update_data
        assert "duration" in update_data
        assert isinstance(update_data["duration"], float)
        assert update_data["duration"] >= 0
