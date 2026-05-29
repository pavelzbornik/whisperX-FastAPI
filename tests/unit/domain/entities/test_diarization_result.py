"""Unit tests for DiarizationResult domain entity."""

import pandas as pd

from app.domain.entities.diarization_result import DiarizationResult


class TestDiarizationResult:
    """Test suite for DiarizationResult entity."""

    def test_has_embeddings_true(self) -> None:
        """Test has_embeddings returns True when embeddings present."""
        result = DiarizationResult(
            segments=pd.DataFrame(),
            speaker_embeddings={"SPEAKER_00": [0.1, 0.2]},
        )
        assert result.has_embeddings() is True

    def test_has_embeddings_false(self) -> None:
        """Test has_embeddings returns False when no embeddings."""
        result = DiarizationResult(segments=pd.DataFrame())
        assert result.has_embeddings() is False

    def test_to_serializable_with_embeddings(self) -> None:
        """Test serialization includes embeddings when present."""
        df = pd.DataFrame(
            [
                {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "segment": None},
                {"start": 1.0, "end": 2.0, "speaker": "SPEAKER_01", "segment": None},
            ]
        )
        embeddings = {"SPEAKER_00": [0.1, 0.2], "SPEAKER_01": [-0.1, -0.2]}
        result = DiarizationResult(segments=df, speaker_embeddings=embeddings)

        serialized = result.to_serializable()
        assert isinstance(serialized, dict)
        assert "segments" in serialized
        assert "speaker_embeddings" in serialized
        assert len(serialized["segments"]) == 2
        assert "segment" not in serialized["segments"][0]
        assert serialized["speaker_embeddings"] == embeddings

    def test_to_serializable_without_embeddings(self) -> None:
        """Test serialization returns list for backward compat when no embeddings."""
        df = pd.DataFrame(
            [
                {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"},
            ]
        )
        result = DiarizationResult(segments=df, speaker_embeddings=None)

        serialized = result.to_serializable()
        assert isinstance(serialized, list)
        assert len(serialized) == 1
        assert serialized[0]["speaker"] == "SPEAKER_00"

    def test_to_serializable_drops_segment_column(self) -> None:
        """Test that the segment column is dropped during serialization."""
        df = pd.DataFrame(
            [{"start": 0.0, "end": 1.0, "speaker": "S0", "segment": "obj"}]
        )
        result = DiarizationResult(segments=df)
        serialized = result.to_serializable()
        assert isinstance(serialized, list)
        assert "segment" not in serialized[0]

    def test_default_speaker_embeddings_is_none(self) -> None:
        """Test default value for speaker_embeddings."""
        result = DiarizationResult(segments=pd.DataFrame())
        assert result.speaker_embeddings is None
