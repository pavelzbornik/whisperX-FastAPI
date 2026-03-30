"""Domain entity for diarization results."""

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class DiarizationResult:
    """Result of a diarization operation.

    Attributes:
        segments: DataFrame with speaker segments (start, end, speaker columns)
        speaker_embeddings: Optional mapping of speaker labels to embedding vectors
    """

    segments: pd.DataFrame
    speaker_embeddings: dict[str, list[float]] | None = None

    def has_embeddings(self) -> bool:
        """Check if embeddings are available."""
        return self.speaker_embeddings is not None

    def to_serializable(self) -> dict[str, Any] | list[Any]:
        """Convert to JSON-serializable format for task result storage.

        Returns dict with segments + embeddings if embeddings present,
        otherwise just the list of segment dicts for backward compatibility.
        """
        segments_list: list[Any] = self.segments.drop(
            columns=["segment"], errors="ignore"
        ).to_dict(orient="records")

        if self.speaker_embeddings:
            return {
                "segments": segments_list,
                "speaker_embeddings": self.speaker_embeddings,
            }
        return segments_list
