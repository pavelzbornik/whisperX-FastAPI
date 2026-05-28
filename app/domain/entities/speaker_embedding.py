"""Domain entity for speaker embeddings."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SpeakerEmbedding:
    """Domain entity representing a speaker embedding for identification.

    Attributes:
        uuid: Unique identifier for the speaker embedding
        speaker_label: User-facing name for the speaker (e.g. "Alice")
        embedding: Vector representation of the speaker's voice
        description: Optional free-text description (role, voice notes, etc.)
        task_uuid: Optional link to the originating diarization task
        created_at: Timestamp of creation
    """

    uuid: str
    speaker_label: str
    embedding: list[float]
    description: str | None = None
    task_uuid: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
