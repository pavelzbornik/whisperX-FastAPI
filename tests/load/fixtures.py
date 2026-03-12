"""Binary fixtures for load tests — loaded once at module import.

All byte buffers are read from ``tests/test_files/`` at import time so locust
worker threads never perform disk I/O during the test itself.
"""

from pathlib import Path

_BASE = Path(__file__).parent.parent / "test_files"

AUDIO_BYTES: bytes = (_BASE / "audio_en.mp3").read_bytes()
TRANSCRIPT_BYTES: bytes = (_BASE / "transcript.json").read_bytes()
ALIGNED_TRANSCRIPT_BYTES: bytes = (_BASE / "aligned_transcript.json").read_bytes()
DIARIZATION_BYTES: bytes = (_BASE / "diarazition.json").read_bytes()
