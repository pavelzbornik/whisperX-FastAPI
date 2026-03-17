"""Unit tests for app/audio.py — process_audio_file exception handling."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.audio import process_audio_file
from app.core.exceptions import AudioProcessingError


@pytest.mark.unit
class TestProcessAudioFile:
    """Unit tests for process_audio_file exception handling."""

    def test_corrupted_audio_raises_audio_processing_error(
        self, tmp_path: Path
    ) -> None:
        """Corrupted/empty audio file raises AudioProcessingError (→ HTTP 400)."""
        corrupt = tmp_path / "empty.mp3"
        corrupt.write_bytes(b"")  # empty file — not a valid audio stream

        with pytest.raises(AudioProcessingError):
            process_audio_file(str(corrupt))

    def test_audio_processing_error_reason_is_safe(self, tmp_path: Path) -> None:
        """AudioProcessingError reason must not contain internal exception detail."""
        corrupt = tmp_path / "corrupt.mp3"
        corrupt.write_bytes(b"\x00\x01\x02")  # invalid audio bytes

        with pytest.raises(AudioProcessingError) as exc_info:
            process_audio_file(str(corrupt))

        err = exc_info.value
        # The user-facing message should be a generic safe string.
        assert err.user_message == (
            "Audio processing failed. Please try again or use a different audio file."
        )
        # The details dict should NOT expose the raw decoder exception text.
        assert (
            "original_error" not in err.details
            or err.details.get("original_error") is None
        )

    def test_os_error_propagates_unchanged(self, tmp_path: Path) -> None:
        """OSError from load_audio re-raises as-is (stays HTTP 500, not 400)."""
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_bytes(b"fake")

        with patch("app.audio.load_audio", side_effect=FileNotFoundError("gone")):
            with pytest.raises(FileNotFoundError):
                process_audio_file(str(audio_path))

    def test_non_os_exception_becomes_audio_processing_error(
        self, tmp_path: Path
    ) -> None:
        """Non-OSError from load_audio is wrapped in AudioProcessingError."""
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_bytes(b"fake")

        with patch("app.audio.load_audio", side_effect=RuntimeError("decode fail")):
            with pytest.raises(AudioProcessingError) as exc_info:
                process_audio_file(str(audio_path))

        # Original exception must NOT appear in the user-facing message.
        assert "decode fail" not in exc_info.value.user_message
