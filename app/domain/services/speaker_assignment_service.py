"""Interface for speaker assignment services using Protocol for structural typing."""

from typing import Any, Protocol

import pandas as pd


class ISpeakerAssignmentService(Protocol):
    """
    Interface for assigning speakers to transcript words/segments.

    Implementations combine diarization results with aligned transcripts to
    assign speaker labels to individual words or segments. This interface
    defines the contract without tying to a specific implementation.

    The Protocol allows structural typing - any class implementing these methods
    with matching signatures will satisfy this interface.
    """

    def assign_speakers(
        self,
        diarization_segments: pd.DataFrame,
        transcript: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Assign speaker labels to transcript words based on diarization.

        Args:
            diarization_segments: DataFrame with speaker segments
                (columns: start, end, speaker)
            transcript: Aligned transcript dictionary with word-level timestamps

        Returns:
            Dictionary containing transcript with speaker labels assigned:
                - segments: List of segments with speaker information
                - word_segments: Words with assigned speakers
        """
        ...
