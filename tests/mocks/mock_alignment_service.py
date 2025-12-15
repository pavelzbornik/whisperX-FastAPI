"""Mock alignment service for testing."""

from typing import Any

import numpy as np


class MockAlignmentService:
    """
    Mock alignment service for testing.

    Returns predefined results without running actual alignment.
    This allows for fast unit testing without the overhead of
    loading and running alignment models.
    """

    def __init__(
        self, mock_result: dict[str, Any] | None = None, should_fail: bool = False
    ) -> None:
        """
        Initialize mock alignment service.

        Args:
            mock_result: Custom result to return (uses default if None)
            should_fail: If True, raises exception on align
        """
        self.mock_result = mock_result or self._default_result()
        self.should_fail = should_fail
        self.align_called = False
        self.align_call_count = 0
        self.load_model_called = False
        self.unload_model_called = False
        self.last_align_params: dict[str, Any] = {}

    def align(
        self,
        transcript: list[dict[str, Any]],
        audio: np.ndarray[Any, np.dtype[np.float32]],
        language_code: str,
        device: str,
        align_model: str | None = None,
        interpolate_method: str = "nearest",
        return_char_alignments: bool = False,
    ) -> dict[str, Any]:
        """
        Return mock alignment result immediately.

        Args:
            transcript: Transcript segments (ignored in mock)
            audio: Audio data (ignored in mock)
            language_code: Language code
            device: Device
            align_model: Alignment model
            interpolate_method: Interpolation method
            return_char_alignments: Whether to return character alignments

        Returns:
            Mock alignment result

        Raises:
            RuntimeError: If should_fail is True
        """
        self.align_called = True
        self.align_call_count += 1
        self.last_align_params = {
            "language_code": language_code,
            "device": device,
            "align_model": align_model,
            "interpolate_method": interpolate_method,
            "return_char_alignments": return_char_alignments,
        }

        if self.should_fail:
            raise RuntimeError("Mock alignment failed")

        return self.mock_result

    def load_model(
        self, language_code: str, device: str, model_name: str | None = None
    ) -> None:
        """
        Mock model loading - does nothing.

        Args:
            language_code: Language code
            device: Device
            model_name: Model name
        """
        self.load_model_called = True

    def unload_model(self) -> None:
        """Mock model unloading - does nothing."""
        self.unload_model_called = True

    def _default_result(self) -> dict[str, Any]:
        """
        Provide default mock alignment result.

        Returns:
            Dictionary mimicking WhisperX alignment output
        """
        return {
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "This is a test",
                    "words": [
                        {"word": "This", "start": 0.0, "end": 0.5, "score": 0.99},
                        {"word": "is", "start": 0.5, "end": 0.8, "score": 0.98},
                        {"word": "a", "start": 0.8, "end": 1.0, "score": 0.97},
                        {"word": "test", "start": 1.0, "end": 2.0, "score": 0.99},
                    ],
                },
                {
                    "start": 2.0,
                    "end": 4.0,
                    "text": "transcription.",
                    "words": [
                        {
                            "word": "transcription.",
                            "start": 2.0,
                            "end": 4.0,
                            "score": 0.99,
                        },
                    ],
                },
            ],
            "word_segments": [
                {"word": "This", "start": 0.0, "end": 0.5, "score": 0.99},
                {"word": "is", "start": 0.5, "end": 0.8, "score": 0.98},
                {"word": "a", "start": 0.8, "end": 1.0, "score": 0.97},
                {"word": "test", "start": 1.0, "end": 2.0, "score": 0.99},
                {"word": "transcription.", "start": 2.0, "end": 4.0, "score": 0.99},
            ],
        }
