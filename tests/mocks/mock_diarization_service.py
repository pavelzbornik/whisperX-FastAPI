"""Mock diarization service for testing."""

from typing import Any

import numpy as np
import pandas as pd

from app.domain.entities.diarization_result import DiarizationResult


class MockDiarizationService:
    """
    Mock diarization service for testing.

    Returns predefined results without running actual diarization.
    This allows for fast unit testing without the overhead of
    loading and running diarization models.
    """

    def __init__(
        self,
        mock_result: pd.DataFrame | None = None,
        mock_embeddings: dict[str, list[float]] | None = None,
        should_fail: bool = False,
    ) -> None:
        """
        Initialize mock diarization service.

        Args:
            mock_result: Custom segments DataFrame to return (uses default if None)
            mock_embeddings: Custom speaker embeddings to return when requested
            should_fail: If True, raises exception on diarize
        """
        self.mock_result = (
            mock_result if mock_result is not None else self._default_result()
        )
        self.mock_embeddings = mock_embeddings or self._default_embeddings()
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
        return_embeddings: bool = False,
    ) -> DiarizationResult:
        """
        Return mock diarization result immediately.

        Args:
            audio: Audio data (ignored in mock)
            device: Device
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers
            return_embeddings: Whether to include speaker embeddings

        Returns:
            DiarizationResult with mock segments and optional embeddings

        Raises:
            RuntimeError: If should_fail is True
        """
        self.diarize_called = True
        self.diarize_call_count += 1
        self.last_diarize_params = {
            "audio": audio,
            "device": device,
            "min_speakers": min_speakers,
            "max_speakers": max_speakers,
            "return_embeddings": return_embeddings,
        }

        if self.should_fail:
            raise RuntimeError("Mock diarization failed")

        return DiarizationResult(
            segments=self.mock_result,
            speaker_embeddings=self.mock_embeddings if return_embeddings else None,
        )

    def load_model(self, _device: str, _hf_token: str) -> None:
        """
        Mock model loading - does nothing.

        Args:
            _device: Device (unused in mock)
            _hf_token: HuggingFace token (unused in mock)
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

    def _default_embeddings(self) -> dict[str, list[float]]:
        """
        Provide default mock speaker embeddings.

        Returns:
            Dictionary mapping speaker labels to embedding vectors
        """
        return {
            "SPEAKER_00": [0.1, 0.2, 0.3, 0.4],
            "SPEAKER_01": [-0.1, -0.2, -0.3, -0.4],
        }
