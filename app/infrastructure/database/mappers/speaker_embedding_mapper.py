"""Mapper functions for converting between domain and ORM speaker embedding models."""

from app.domain.entities.speaker_embedding import (
    SpeakerEmbedding as DomainSpeakerEmbedding,
)
from app.infrastructure.database.models import SpeakerEmbedding as ORMSpeakerEmbedding


def to_domain(orm_embedding: ORMSpeakerEmbedding) -> DomainSpeakerEmbedding:
    """
    Convert an ORM SpeakerEmbedding model to a domain entity.

    Args:
        orm_embedding: The SQLAlchemy ORM SpeakerEmbedding model

    Returns:
        DomainSpeakerEmbedding: The domain SpeakerEmbedding entity
    """
    return DomainSpeakerEmbedding(
        uuid=orm_embedding.uuid,
        task_uuid=orm_embedding.task_uuid,
        speaker_label=orm_embedding.speaker_label,
        description=orm_embedding.description,
        embedding=orm_embedding.embedding,
        created_at=orm_embedding.created_at,
    )


def to_orm(domain_embedding: DomainSpeakerEmbedding) -> ORMSpeakerEmbedding:
    """
    Convert a domain SpeakerEmbedding entity to an ORM model.

    Args:
        domain_embedding: The domain SpeakerEmbedding entity

    Returns:
        ORMSpeakerEmbedding: The SQLAlchemy ORM SpeakerEmbedding model
    """
    return ORMSpeakerEmbedding(
        uuid=domain_embedding.uuid,
        task_uuid=domain_embedding.task_uuid,
        speaker_label=domain_embedding.speaker_label,
        description=domain_embedding.description,
        embedding=domain_embedding.embedding,
        created_at=domain_embedding.created_at,
    )
