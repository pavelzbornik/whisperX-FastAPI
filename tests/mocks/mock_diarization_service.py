"""Mock diarization service for testing."""

from typing import Any

import numpy as np
import pandas as pd


class MockDiarizationService:
    """
    Mock diarization service for testing.

    Returns predefined results without running actual diarization.
    This allows for fast unit testing without the overhead of
    loading and running diarization models.
    """

    def __init__(
        self, mock_result: pd.DataFrame | None = None, should_fail: bool = False
    ) -> None:
        """
        Initialize mock diarization service.

        Args:
            mock_result: Custom result to return (uses default if None)
            should_fail: If True, raises exception on diarize
        """
        self.mock_result = (
            mock_result if mock_result is not None else self._default_result()
        )
        self.should_fail = should_fail
        self.diarize_called = False
        self.diarize_call_count = 0
        self.load_model_called = False
        self.unload_model_called = False
        self.last_diarize_params: dict[str, Any] = {}

    def diarize(
        self,
        audio: np.ndarray[Any, np.dtype[np.float32]],
        device: str,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> pd.DataFrame:
        """
        Return mock diarization result immediately.

        Args:
            audio: Audio data (ignored in mock)
            device: Device
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers

        Returns:
            Mock diarization DataFrame

        Raises:
            RuntimeError: If should_fail is True
        """
        self.diarize_called = True
        self.diarize_call_count += 1
        self.last_diarize_params = {
            "device": device,
            "min_speakers": min_speakers,
            "max_speakers": max_speakers,
        }

        if self.should_fail:
            raise RuntimeError("Mock diarization failed")

        return self.mock_result

    def load_model(self, device: str, hf_token: str) -> None:
        """
        Mock model loading - does nothing.

        Args:
            device: Device
            hf_token: HuggingFace token
        """
        self.load_model_called = True

    def unload_model(self) -> None:
        """Mock model unloading - does nothing."""
        self.unload_model_called = True

    def _default_result(self) -> pd.DataFrame:
        """
        Provide default mock diarization result.

        Returns:
            DataFrame mimicking PyAnnote diarization output
        """
        return pd.DataFrame(
            [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "speaker": "SPEAKER_00",
                },
                {
                    "start": 2.0,
                    "end": 4.0,
                    "speaker": "SPEAKER_01",
                },
            ]
        )
