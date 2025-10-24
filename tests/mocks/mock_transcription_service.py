"""Mock transcription service for testing."""

from typing import Any

import numpy as np


class MockTranscriptionService:
    """
    Mock transcription service for testing.

    Returns predefined results without running actual ML operations.
    This allows for fast unit testing of business logic without
    the overhead of loading and running ML models.
    """

    def __init__(
        self, mock_result: dict[str, Any] | None = None, should_fail: bool = False
    ) -> None:
        """
        Initialize mock transcription service.

        Args:
            mock_result: Custom result to return (uses default if None)
            should_fail: If True, raises exception on transcribe
        """
        self.mock_result = mock_result or self._default_result()
        self.should_fail = should_fail
        self.transcribe_called = False
        self.transcribe_call_count = 0
        self.load_model_called = False
        self.unload_model_called = False
        self.last_transcribe_params: dict[str, Any] = {}

    def transcribe(
        self,
        audio: np.ndarray[Any, np.dtype[np.float32]],
        task: str,
        asr_options: dict[str, Any],
        vad_options: dict[str, Any],
        language: str,
        batch_size: int,
        chunk_size: int,
        model: str,
        device: str,
        device_index: int,
        compute_type: str,
        threads: int,
    ) -> dict[str, Any]:
        """
        Return mock transcription result immediately.

        Args:
            audio: Audio data (ignored in mock)
            task: Task type
            asr_options: ASR options
            vad_options: VAD options
            language: Language code
            batch_size: Batch size
            chunk_size: Chunk size
            model: Model name
            device: Device
            device_index: Device index
            compute_type: Compute type
            threads: Thread count

        Returns:
            Mock transcription result

        Raises:
            RuntimeError: If should_fail is True
        """
        self.transcribe_called = True
        self.transcribe_call_count += 1
        self.last_transcribe_params = {
            "task": task,
            "language": language,
            "model": model,
            "device": device,
            "batch_size": batch_size,
            "chunk_size": chunk_size,
            "compute_type": compute_type,
            "threads": threads,
        }

        if self.should_fail:
            raise RuntimeError("Mock transcription failed")

        return self.mock_result

    def load_model(
        self,
        model_name: str,
        device: str,
        device_index: int,
        compute_type: str,
        asr_options: dict[str, Any],
        vad_options: dict[str, Any],
        language: str,
        task: str,
        threads: int,
    ) -> None:
        """
        Mock model loading - does nothing.

        Args:
            model_name: Model name
            device: Device
            device_index: Device index
            compute_type: Compute type
            asr_options: ASR options
            vad_options: VAD options
            language: Language
            task: Task type
            threads: Thread count
        """
        self.load_model_called = True

    def unload_model(self) -> None:
        """Mock model unloading - does nothing."""
        self.unload_model_called = True

    def _default_result(self) -> dict[str, Any]:
        """
        Provide default mock transcription result.

        Returns:
            Dictionary mimicking WhisperX transcription output
        """
        return {
            "text": "This is a test transcription.",
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "This is a test",
                },
                {
                    "start": 2.0,
                    "end": 4.0,
                    "text": "transcription.",
                },
            ],
            "language": "en",
        }
