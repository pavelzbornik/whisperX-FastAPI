"""Tests for the whisperx_services module."""

from unittest.mock import Mock, patch

import pandas as pd
import pytest
import torch

from app.schemas import (
    AlignmentParams,
    ASROptions,
    ComputeType,
    Device,
    DiarizationParams,
    InterpolateMethod,
    SpeechToTextProcessingParams,
    TaskEnum,
    VADOptions,
    WhisperModel,
    WhisperModelParams,
)
from app.whisperx_services import (
    align_whisper_output,
    device,
    diarize,
    process_audio_common,
    transcribe_with_whisper,
)


@pytest.fixture
def audio_data():
    """Mock audio data for testing."""
    return torch.randn(
        16000
    ).numpy()  # Convert to numpy array - 1 second of audio at 16kHz


@pytest.fixture
def mock_whisper_model():
    """Mock Whisper model for testing."""
    mock = Mock()
    mock.transcribe.return_value = {
        "text": "Test transcription",
        "segments": [],
        "language": "en",
    }
    return mock


@pytest.fixture
def mock_align_model():
    """Mock align model for testing."""
    return Mock()


@pytest.fixture
def mock_diarization_pipeline():
    """Mock diarization pipeline for testing."""
    mock = Mock()
    # Create DataFrame with test data
    mock.return_value = pd.DataFrame(
        [
            {
                "start": 0.0,
                "end": 1.0,
                "speaker": "SPEAKER_00",
                "label": "A",
                "segment": None,  # Will be removed in processing
            }
        ]
    )
    return mock


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_transcribe_with_whisper_gpu(audio_data, mock_whisper_model):
    """Test transcribe_with_whisper function with GPU or fallback to CPU."""
    with patch("app.whisperx_services.load_model", return_value=mock_whisper_model):
        result = transcribe_with_whisper(
            audio=audio_data,
            task="transcribe",
            asr_options={},
            vad_options={},
            language="en",
            model=WhisperModel.tiny,  # Use string value directly
            device="cuda",
            compute_type="float16",
        )

        assert result is not None
        assert "text" in result
        assert "segments" in result
        assert "language" in result


def test_transcribe_with_whisper_cpu(audio_data, mock_whisper_model):
    """Test transcribe_with_whisper function with CPU."""
    with patch("app.whisperx_services.load_model", return_value=mock_whisper_model):
        result = transcribe_with_whisper(
            audio=audio_data,
            task="transcribe",
            asr_options={},
            vad_options={},
            language="en",
            model=WhisperModel.tiny,  # Use string value directly
            device="cpu",
            compute_type="float32",
        )

        assert result is not None
        assert "text" in result
        assert "segments" in result
        assert "language" in result


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_diarize_gpu(audio_data, mock_diarization_pipeline):
    """Test diarize function with GPU."""
    with patch("whisperx.DiarizationPipeline", return_value=mock_diarization_pipeline):
        result = diarize(
            audio=audio_data, device=Device.cuda, min_speakers=1, max_speakers=2
        )

        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert all(isinstance(segment, pd.Series) for _, segment in result.iterrows())
        assert "segment" in result.columns  # Check if column exists
        assert result["segment"].isna().all()  # Verify segment column is all None


def test_align_whisper_output(audio_data, mock_align_model):
    """Test align_whisper_output function."""
    transcript = [{"text": "Test", "start": 0.0, "end": 1.0}]

    with patch(
        "app.whisperx_services.load_align_model", return_value=(mock_align_model, {})
    ):
        with patch(
            "app.whisperx_services.align", return_value={"segments": transcript}
        ):
            result = align_whisper_output(
                transcript=transcript,
                audio=audio_data,
                language_code="en",
                device=device,
                interpolate_method="nearest",
            )

            assert result is not None
            assert "segments" in result
            assert isinstance(result["segments"], list)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_process_audio_common_gpu(
    audio_data, mock_whisper_model, mock_align_model, mock_diarization_pipeline
):
    """Test process_audio_common function with GPU."""
    params = SpeechToTextProcessingParams(
        audio=audio_data,  # Already numpy array from fixture
        identifier="test-123",
        whisper_model_params=WhisperModelParams(
            language="en",
            model=WhisperModel.tiny,  # Use string value directly
            device=Device.cuda,
            compute_type=ComputeType.float16,
            task=TaskEnum.transcribe,
            threads=0,
            batch_size=8,
            chunk_size=20,
        ),
        asr_options=ASROptions(
            beam_size=5,
            best_of=5,
            patience=1,
            length_penalty=1,
            temperatures=0.0,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
            initial_prompt=None,
            suppress_tokens=[-1],
            suppress_numerals=True,
            hotwords=None,
        ),
        vad_options=VADOptions(vad_onset=0.5, vad_offset=0.363),
        alignment_params=AlignmentParams(
            align_model=None,
            interpolate_method=InterpolateMethod.nearest,
            return_char_alignments=False,
        ),
        diarization_params=DiarizationParams(min_speakers=1, max_speakers=2),
    )

    mock_session = Mock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = Mock()
    with patch("app.whisperx_services.load_model", return_value=mock_whisper_model):
        with patch(
            "app.whisperx_services.load_align_model",
            return_value=(mock_align_model, {}),
        ):
            with patch(
                "whisperx.DiarizationPipeline", return_value=mock_diarization_pipeline
            ):
                with patch(
                    "app.whisperx_services.align",
                    return_value={"segments": [], "word_segments": []},
                ):
                    with patch(
                        "app.whisperx_services.assign_word_speakers",
                        return_value={"segments": [], "word_segments": []},
                    ):
                        process_audio_common(params, session=mock_session)
                        # The function updates task status in DB, no return value to assert
                        # Success is indicated by no exceptions being raised


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_gpu_memory_logging():
    """Test GPU memory logging when available."""
    if torch.cuda.is_available():
        mock_model = Mock()
        mock_model.transcribe.return_value = {
            "text": "Test transcription",
            "segments": [],
            "language": "en",
        }

        with patch("app.whisperx_services.logger.debug") as mock_logger:
            with patch("app.whisperx_services.load_model", return_value=mock_model):
                audio_data = torch.randn(16000).numpy()  # Convert to numpy array
                transcribe_with_whisper(
                    audio=audio_data,
                    task="transcribe",
                    asr_options={},
                    vad_options={},
                    language="en",
                    model=WhisperModel.tiny,  # Use string value directly
                    device=Device.cuda,
                    compute_type=ComputeType.float16,
                )

                # Verify that GPU memory logging calls were made
                # Check if any debug call contains "GPU memory after cleanup"
                cleanup_calls = [
                    call_args[0][0]
                    for call_args in mock_logger.call_args_list
                    if "GPU memory after cleanup" in call_args[0][0]
                ]
                assert len(cleanup_calls) > 0, (
                    "No GPU memory cleanup logging call found"
                )


def test_error_handling():
    """Test error handling in whisperx services."""
    with pytest.raises(ValueError):
        # Test with invalid compute type for CPU
        audio_data = torch.randn(16000).numpy()  # Convert to numpy array
        transcribe_with_whisper(
            audio=audio_data,
            task="transcribe",
            asr_options={},
            vad_options={},
            language="en",
            model=WhisperModel.tiny,  # Use string value directly
            device=Device.cpu,
            compute_type=ComputeType.float16,  # This should raise an error on CPU
        )
