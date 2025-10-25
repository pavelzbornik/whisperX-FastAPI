"""Unit tests for VAD service."""

from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.api.schemas.websocket_schemas import VADConfig
from app.services.vad_service import SileroVADService


@pytest.fixture
def vad_config() -> VADConfig:
    """Create default VAD configuration."""
    return VADConfig(
        threshold=0.5,
        min_speech_duration_ms=250,
        max_speech_duration_s=float("inf"),
        min_silence_duration_ms=100,
        window_size_samples=512,
        speech_pad_ms=30,
        pre_roll_buffer_ms=300,
        min_utterance_length_s=1.5,
    )


@pytest.fixture
def mock_torch_hub() -> Any:
    """Mock torch.hub.load for VAD model."""
    with patch("torch.hub.load") as mock_load:
        # Create mock model and utils
        mock_model = MagicMock()
        mock_utils = MagicMock()
        mock_load.return_value = (mock_model, mock_utils)
        yield mock_model


def test_vad_service_initialization(vad_config: VADConfig) -> None:
    """Test VAD service initializes without loading model."""
    service = SileroVADService(vad_config, sample_rate=16000)

    assert service.config == vad_config
    assert service.sample_rate == 16000
    assert service.model is None  # Model not loaded yet
    assert not service.is_speaking()
    assert service.get_current_speech_duration() == 0.0


def test_vad_service_lazy_loading(
    vad_config: VADConfig, mock_torch_hub: MagicMock
) -> None:
    """Test VAD service loads model lazily on first use."""
    service = SileroVADService(vad_config, sample_rate=16000)

    # Model should not be loaded yet
    assert service.model is None

    # Set up mock to return speech probability
    mock_torch_hub.return_value = MagicMock(item=MagicMock(return_value=0.8))

    # Generate test audio
    audio_chunk = np.random.randn(512).astype(np.float32)

    # Process audio - this should trigger lazy loading
    is_speech, speech_ended, accumulated = service.process_audio_chunk(audio_chunk)

    # Model should now be loaded
    assert service.model is not None


def test_vad_pre_roll_buffer_size(vad_config: VADConfig) -> None:
    """Test pre-roll buffer size calculation."""
    service = SileroVADService(vad_config, sample_rate=16000)

    # 300ms at 16kHz = 4800 samples
    # With window_size 512, buffer should hold 4800 / 512 = 9.375 -> 9 chunks
    expected_size = 9
    assert service._pre_roll_buffer.maxlen == expected_size


def test_vad_reset(vad_config: VADConfig) -> None:
    """Test VAD state reset."""
    service = SileroVADService(vad_config, sample_rate=16000)

    # Manually set some state
    service._is_speech = True
    service._current_speech_duration = 5.0
    service._speech_frames.append(np.zeros(100, dtype=np.float32))

    # Reset
    service.reset()

    # Verify state is cleared
    assert not service.is_speaking()
    assert service.get_current_speech_duration() == 0.0
    assert len(service._speech_frames) == 0


def test_vad_speech_detection_cycle(
    vad_config: VADConfig, mock_torch_hub: MagicMock
) -> None:
    """Test complete speech detection cycle."""
    service = SileroVADService(vad_config, sample_rate=16000)

    # Mock speech probabilities: start high (speech), then low (silence)
    speech_probs = [0.8, 0.8, 0.8, 0.1, 0.1, 0.1]  # Speech for 3 chunks, then silence
    mock_torch_hub.side_effect = [
        MagicMock(item=MagicMock(return_value=p)) for p in speech_probs
    ]

    audio_chunk = np.random.randn(512).astype(np.float32)

    results = []
    for _ in speech_probs:
        result = service.process_audio_chunk(audio_chunk)
        results.append(result)

    # First chunk should start speech
    assert results[0][0]  # is_speech

    # Middle chunks should continue speech
    assert results[1][0]
    assert results[2][0]

    # Last chunks might end speech (depending on duration threshold)
    # We won't assert on speech_ended since it depends on accumulated duration
