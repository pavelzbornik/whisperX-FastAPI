"""Mock speaker assignment service for testing."""

from typing import Any

import pandas as pd


class MockSpeakerAssignmentService:
    """
    Mock speaker assignment service for testing.

    Returns predefined results without running actual speaker assignment.
    This allows for fast unit testing without any ML overhead.
    """

    def __init__(
        self, mock_result: dict[str, Any] | None = None, should_fail: bool = False
    ) -> None:
        """
        Initialize mock speaker assignment service.

        Args:
            mock_result: Custom result to return (uses default if None)
            should_fail: If True, raises exception on assign_speakers
        """
        self.mock_result = mock_result or self._default_result()
        self.should_fail = should_fail
        self.assign_speakers_called = False
        self.assign_speakers_call_count = 0
        self.last_assign_params: dict[str, Any] = {}

    def assign_speakers(
        self,
        diarization_segments: pd.DataFrame,
        transcript: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Return mock speaker assignment result immediately.

        Args:
            diarization_segments: Diarization DataFrame (ignored in mock)
            transcript: Transcript dictionary (ignored in mock)

        Returns:
            Mock speaker assignment result

        Raises:
            RuntimeError: If should_fail is True
        """
        self.assign_speakers_called = True
        self.assign_speakers_call_count += 1
        self.last_assign_params = {
            "diarization_segments_shape": diarization_segments.shape,
            "transcript_keys": list(transcript.keys()),
        }

        if self.should_fail:
            raise RuntimeError("Mock speaker assignment failed")

        return self.mock_result

    def _default_result(self) -> dict[str, Any]:
        """
        Provide default mock speaker assignment result.

        Returns:
            Dictionary mimicking WhisperX speaker assignment output
        """
        return {
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "This is a test",
                    "speaker": "SPEAKER_00",
                    "words": [
                        {
                            "word": "This",
                            "start": 0.0,
                            "end": 0.5,
                            "score": 0.99,
                            "speaker": "SPEAKER_00",
                        },
                        {
                            "word": "is",
                            "start": 0.5,
                            "end": 0.8,
                            "score": 0.98,
                            "speaker": "SPEAKER_00",
                        },
                        {
                            "word": "a",
                            "start": 0.8,
                            "end": 1.0,
                            "score": 0.97,
                            "speaker": "SPEAKER_00",
                        },
                        {
                            "word": "test",
                            "start": 1.0,
                            "end": 2.0,
                            "score": 0.99,
                            "speaker": "SPEAKER_00",
                        },
                    ],
                },
                {
                    "start": 2.0,
                    "end": 4.0,
                    "text": "transcription.",
                    "speaker": "SPEAKER_01",
                    "words": [
                        {
                            "word": "transcription.",
                            "start": 2.0,
                            "end": 4.0,
                            "score": 0.99,
                            "speaker": "SPEAKER_01",
                        },
                    ],
                },
            ],
            "word_segments": [
                {
                    "word": "This",
                    "start": 0.0,
                    "end": 0.5,
                    "score": 0.99,
                    "speaker": "SPEAKER_00",
                },
                {
                    "word": "is",
                    "start": 0.5,
                    "end": 0.8,
                    "score": 0.98,
                    "speaker": "SPEAKER_00",
                },
                {
                    "word": "a",
                    "start": 0.8,
                    "end": 1.0,
                    "score": 0.97,
                    "speaker": "SPEAKER_00",
                },
                {
                    "word": "test",
                    "start": 1.0,
                    "end": 2.0,
                    "score": 0.99,
                    "speaker": "SPEAKER_00",
                },
                {
                    "word": "transcription.",
                    "start": 2.0,
                    "end": 4.0,
                    "score": 0.99,
                    "speaker": "SPEAKER_01",
                },
            ],
        }
