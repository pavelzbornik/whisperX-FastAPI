"""Tests for the services module."""

from datetime import datetime
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from fastapi import HTTPException

from app.schemas import (
    AlignmentParams,
    ASROptions,
    Device,
    DiarizationParams,
    InterpolateMethod,
    TaskEnum,
    TaskStatus,
    VADOptions,
    WhisperModel,
    WhisperModelParams,
)
from app.services import (
    process_alignment,
    process_audio_task,
    process_diarize,
    process_speaker_assignment,
    process_transcribe,
    validate_language_code,
)


class TestValidateLanguageCode:
    """Test cases for validate_language_code function."""

    @patch("app.services.whisperx.utils.LANGUAGES", {"en", "es", "fr", "de"})
    def test_validate_language_code_valid(self):
        """Test validation with valid language codes."""
        # Should not raise exception
        validate_language_code("en")
        validate_language_code("es") 
        validate_language_code("fr")
        validate_language_code("de")

    @patch("app.services.whisperx.utils.LANGUAGES", {"en", "es", "fr"})
    def test_validate_language_code_invalid(self):
        """Test validation with invalid language code."""
        with pytest.raises(HTTPException) as exc_info:
            validate_language_code("invalid_lang")
        
        assert exc_info.value.status_code == 400
        assert "Invalid language code: invalid_lang" in str(exc_info.value.detail)

    @patch("app.services.whisperx.utils.LANGUAGES", {"en", "es", "fr"})
    def test_validate_language_code_empty(self):
        """Test validation with empty language code."""
        with pytest.raises(HTTPException) as exc_info:
            validate_language_code("")
        
        assert exc_info.value.status_code == 400
        assert "Invalid language code: " in str(exc_info.value.detail)

    @patch("app.services.whisperx.utils.LANGUAGES", {"en", "es", "fr", "zh"})
    def test_validate_language_code_case_sensitive(self):
        """Test that language code validation is case sensitive."""
        # Valid lowercase
        validate_language_code("en")
        
        # Invalid uppercase should fail
        with pytest.raises(HTTPException):
            validate_language_code("EN")


class TestProcessAudioTask:
    """Test cases for process_audio_task function."""

    @patch("app.services.update_task_status_in_db")
    @patch("app.services.logger")
    @patch("app.services.datetime")
    def test_process_audio_task_success(self, mock_datetime, mock_logger, mock_update_task):
        """Test successful audio task processing."""
        # Mock datetime
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        end_time = datetime(2023, 1, 1, 12, 0, 5)  # 5 seconds later
        mock_datetime.now.side_effect = [start_time, end_time]
        
        # Mock audio processor
        mock_processor = Mock()
        mock_processor.return_value = {"result": "test_result"}
        
        # Mock session
        mock_session = Mock()
        
        # Call the function
        process_audio_task(
            mock_processor,
            "test-123",
            "transcription",
            mock_session,
            "arg1", "arg2"
        )
        
        # Verify processor was called with correct arguments
        mock_processor.assert_called_once_with("arg1", "arg2")
        
        # Verify logging
        mock_logger.info.assert_any_call("Starting transcription task for identifier test-123")
        mock_logger.info.assert_any_call("Completed transcription task for identifier test-123. Duration: 5.0s")
        
        # Verify task status update
        mock_update_task.assert_called_once_with(
            identifier="test-123",
            update_data={
                "status": TaskStatus.completed,
                "result": {"result": "test_result"},
                "duration": 5.0,
                "start_time": start_time,
                "end_time": end_time,
            },
            session=mock_session,
        )

    @patch("app.services.update_task_status_in_db")
    @patch("app.services.logger")
    def test_process_audio_task_diarization_result_processing(self, mock_logger, mock_update_task):
        """Test that diarization results are processed correctly."""
        # Mock DataFrame result for diarization
        mock_df = pd.DataFrame({
            'start': [0.0, 1.0],
            'end': [1.0, 2.0],
            'speaker': ['SPEAKER_00', 'SPEAKER_01'],
            'segment': [None, None]  # This column should be dropped
        })
        
        mock_processor = Mock()
        mock_processor.return_value = mock_df
        
        mock_session = Mock()
        
        process_audio_task(
            mock_processor,
            "test-123",
            "diarization",  # Special task type
            mock_session,
        )
        
        # Verify the result was processed (segment column dropped and converted to dict)
        expected_result = [
            {'start': 0.0, 'end': 1.0, 'speaker': 'SPEAKER_00'},
            {'start': 1.0, 'end': 2.0, 'speaker': 'SPEAKER_01'}
        ]
        
        mock_update_task.assert_called_once()
        call_args = mock_update_task.call_args[1]
        assert call_args["update_data"]["result"] == expected_result

    @patch("app.services.update_task_status_in_db")
    @patch("app.services.logger")
    def test_process_audio_task_value_error(self, mock_logger, mock_update_task):
        """Test handling of ValueError in audio task processing."""
        mock_processor = Mock()
        mock_processor.side_effect = ValueError("Test value error")
        
        mock_session = Mock()
        
        process_audio_task(
            mock_processor,
            "test-123",
            "transcription",
            mock_session,
        )
        
        # Verify error logging
        mock_logger.error.assert_called_once_with(
            "Task transcription failed for identifier test-123. Error: Test value error"
        )
        
        # Verify task status update with error
        mock_update_task.assert_called_once_with(
            identifier="test-123",
            update_data={"status": TaskStatus.failed, "error": "Test value error"},
            session=mock_session,
        )

    @patch("app.services.update_task_status_in_db")
    @patch("app.services.logger")
    def test_process_audio_task_type_error(self, mock_logger, mock_update_task):
        """Test handling of TypeError in audio task processing."""
        mock_processor = Mock()
        mock_processor.side_effect = TypeError("Test type error")
        
        mock_session = Mock()
        
        process_audio_task(
            mock_processor,
            "test-456",
            "alignment",
            mock_session,
        )
        
        mock_logger.error.assert_called_once_with(
            "Task alignment failed for identifier test-456. Error: Test type error"
        )

    @patch("app.services.update_task_status_in_db")
    @patch("app.services.logger")
    def test_process_audio_task_runtime_error(self, mock_logger, mock_update_task):
        """Test handling of RuntimeError in audio task processing."""
        mock_processor = Mock()
        mock_processor.side_effect = RuntimeError("Test runtime error")
        
        mock_session = Mock()
        
        process_audio_task(
            mock_processor,
            "test-789",
            "diarization",
            mock_session,
        )
        
        mock_logger.error.assert_called_once_with(
            "Task diarization failed for identifier test-789. Error: Test runtime error"
        )

    @patch("app.services.update_task_status_in_db")
    @patch("app.services.logger")
    def test_process_audio_task_memory_error(self, mock_logger, mock_update_task):
        """Test handling of MemoryError in audio task processing."""
        mock_processor = Mock()
        mock_processor.side_effect = MemoryError("Out of memory")
        
        mock_session = Mock()
        
        process_audio_task(
            mock_processor,
            "test-mem",
            "transcription",
            mock_session,
        )
        
        # Verify memory error specific logging
        mock_logger.error.assert_called_once_with(
            "Task transcription failed for identifier test-mem due to out of memory. Error: Out of memory"
        )
        
        # Verify task status update with memory error
        mock_update_task.assert_called_once_with(
            identifier="test-mem",
            update_data={"status": TaskStatus.failed, "error": "Out of memory"},
            session=mock_session,
        )


class TestProcessTranscribe:
    """Test cases for process_transcribe function."""

    @patch("app.services.process_audio_task")
    @patch("app.services.transcribe_with_whisper")
    def test_process_transcribe(self, mock_transcribe, mock_process_task):
        """Test transcribe processing."""
        # Create test parameters
        model_params = WhisperModelParams(
            language="en",
            model=WhisperModel.tiny,
            device=Device.cpu,
            task=TaskEnum.transcribe,
            batch_size=8,
            chunk_size=20,
        )
        
        asr_options = ASROptions(
            beam_size=5,
            best_of=5,
            patience=1,
        )
        
        vad_options = VADOptions(
            vad_onset=0.5,
            vad_offset=0.363,
        )
        
        mock_audio = "mock_audio_data"
        mock_session = Mock()
        
        process_transcribe(
            mock_audio,
            "test-transcribe",
            model_params,
            asr_options,
            vad_options,
            mock_session
        )
        
        # Verify process_audio_task was called (arguments may vary due to pydantic serialization)
        mock_process_task.assert_called_once()
        call_args = mock_process_task.call_args
        
        # Verify key arguments
        assert call_args[0][0] == mock_transcribe  # audio_processor
        assert call_args[0][1] == "test-transcribe"  # identifier
        assert call_args[0][2] == "transcription"  # task_type
        assert call_args[0][3] == mock_session  # session
        assert call_args[0][4] == mock_audio  # audio


class TestProcessDiarize:
    """Test cases for process_diarize function."""

    @patch("app.services.process_audio_task")
    @patch("app.services.diarize")
    def test_process_diarize(self, mock_diarize, mock_process_task):
        """Test diarization processing."""
        diarize_params = DiarizationParams(
            min_speakers=1,
            max_speakers=3,
        )
        
        mock_audio = "mock_audio_data"
        mock_device = Device.cpu
        mock_session = Mock()
        
        process_diarize(
            mock_audio,
            "test-diarize",
            mock_device,
            diarize_params,
            mock_session
        )
        
        # Verify process_audio_task was called with correct arguments
        mock_process_task.assert_called_once_with(
            mock_diarize,
            "test-diarize",
            "diarization",
            mock_session,
            mock_audio,
            mock_device,
            1,  # min_speakers
            3,  # max_speakers
        )


class TestProcessAlignment:
    """Test cases for process_alignment function."""

    @patch("app.services.process_audio_task")
    @patch("app.services.align_whisper_output")
    def test_process_alignment(self, mock_align, mock_process_task):
        """Test alignment processing."""
        align_params = AlignmentParams(
            align_model=None,
            interpolate_method=InterpolateMethod.nearest,
            return_char_alignments=False,
        )
        
        mock_audio = "mock_audio_data"
        mock_transcript = {
            "segments": [{"text": "test", "start": 0.0, "end": 1.0}],
            "language": "en"
        }
        mock_device = Device.cuda
        mock_session = Mock()
        
        process_alignment(
            mock_audio,
            mock_transcript,
            "test-align",
            mock_device,
            align_params,
            mock_session
        )
        
        # Verify process_audio_task was called with correct arguments
        mock_process_task.assert_called_once_with(
            mock_align,
            "test-align",
            "transcription_alignment",
            mock_session,
            mock_transcript["segments"],  # transcript segments
            mock_audio,
            "en",  # language from transcript
            mock_device,
            None,  # align_model
            InterpolateMethod.nearest,  # interpolate_method
            False,  # return_char_alignments
        )


class TestProcessSpeakerAssignment:
    """Test cases for process_speaker_assignment function."""

    @patch("app.services.process_audio_task")
    @patch("app.services.whisperx.assign_word_speakers")
    def test_process_speaker_assignment(self, mock_assign_speakers, mock_process_task):
        """Test speaker assignment processing."""
        mock_diarization_segments = [
            {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}
        ]
        
        mock_transcript = {
            "segments": [{"text": "test", "start": 0.0, "end": 1.0}]
        }
        
        mock_session = Mock()
        
        process_speaker_assignment(
            mock_diarization_segments,
            mock_transcript,
            "test-speaker",
            mock_session
        )
        
        # Verify process_audio_task was called with correct arguments
        mock_process_task.assert_called_once_with(
            mock_assign_speakers,
            "test-speaker",
            "combine_transcript&diarization",
            mock_session,
            mock_diarization_segments,
            mock_transcript,
        )

    @patch("app.services.process_audio_task")
    def test_process_speaker_assignment_empty_segments(self, mock_process_task):
        """Test speaker assignment with empty diarization segments."""
        mock_diarization_segments = []
        mock_transcript = {"segments": []}
        mock_session = Mock()
        
        process_speaker_assignment(
            mock_diarization_segments,
            mock_transcript,
            "test-empty",
            mock_session
        )
        
        # Should still call process_audio_task
        assert mock_process_task.call_count == 1