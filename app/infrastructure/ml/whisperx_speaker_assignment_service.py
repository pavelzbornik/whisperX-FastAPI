"""WhisperX implementation of speaker assignment service."""

from typing import Any

import pandas as pd
import whisperx

from app.core.logging import logger


class WhisperXSpeakerAssignmentService:
    """
    WhisperX-based implementation of speaker assignment service.

    This service wraps the WhisperX speaker assignment functionality to
    combine diarization results with aligned transcripts.
    """

    def __init__(self) -> None:
        """Initialize the speaker assignment service."""
        self.logger = logger

    def assign_speakers(
        self,
        diarization_segments: pd.DataFrame,
        transcript: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Assign speaker labels to transcript words using WhisperX.

        Args:
            diarization_segments: DataFrame with speaker segments
            transcript: Aligned transcript dictionary

        Returns:
            Dictionary containing transcript with speaker labels
        """
        self.logger.debug("Starting to combine transcript with diarization results")

        result = whisperx.assign_word_speakers(diarization_segments, transcript)

        self.logger.debug("Completed combining transcript with diarization results")

        return result  # type: ignore[no-any-return]
