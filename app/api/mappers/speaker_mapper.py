"""Mapper for converting between speaker API DTOs and domain entities."""

from app.api.schemas.speaker_schemas import SpeakerResponse
from app.domain.entities.speaker_embedding import SpeakerEmbedding


class SpeakerMapper:
    """Mapper for converting between Speaker DTOs and domain entities."""

    @staticmethod
    def to_response(entity: SpeakerEmbedding) -> SpeakerResponse:
        """
        Convert domain SpeakerEmbedding entity to API SpeakerResponse DTO.

        Args:
            entity: The domain SpeakerEmbedding entity

        Returns:
            SpeakerResponse: The API response DTO
        """
        return SpeakerResponse(
            uuid=entity.uuid,
            task_uuid=entity.task_uuid,
            speaker_label=entity.speaker_label,
            description=entity.description,
            embedding=entity.embedding,
            created_at=entity.created_at,
        )
