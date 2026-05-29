"""SQLAlchemy implementations of the ISpeakerEmbeddingRepository interface."""

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseOperationError
from app.core.logging import logger
from app.domain.entities.speaker_embedding import (
    SpeakerEmbedding as DomainSpeakerEmbedding,
)
from app.infrastructure.database.mappers.speaker_embedding_mapper import (
    to_domain,
    to_orm,
)
from app.infrastructure.database.models import SpeakerEmbedding as ORMSpeakerEmbedding


class AsyncSQLAlchemySpeakerEmbeddingRepository:
    """
    Async SQLAlchemy implementation of the ISpeakerEmbeddingRepository interface.

    Used for request-scoped operations (FastAPI route handlers via DI).
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize the repository with an async database session.

        Args:
            session: The SQLAlchemy AsyncSession
        """
        self.session = session

    async def add(self, embedding: DomainSpeakerEmbedding) -> str:
        """
        Add a new speaker embedding to the database.

        Args:
            embedding: The SpeakerEmbedding entity to add

        Returns:
            UUID of the created embedding
        """
        try:
            orm_embedding = to_orm(embedding)
            self.session.add(orm_embedding)
            await self.session.commit()
            await self.session.refresh(orm_embedding)
            logger.info("Speaker embedding added: %s", orm_embedding.uuid)
            return str(orm_embedding.uuid)
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error("Failed to add speaker embedding: %s", str(e))
            raise DatabaseOperationError(
                operation="add_speaker_embedding",
                reason=str(e),
                original_error=e,
            )

    async def get_by_id(self, uuid: str) -> DomainSpeakerEmbedding | None:
        """
        Retrieve a speaker embedding by UUID.

        Args:
            uuid: The unique identifier

        Returns:
            The speaker embedding entity, or None if not found
        """
        try:
            stmt = select(ORMSpeakerEmbedding).where(ORMSpeakerEmbedding.uuid == uuid)
            result = await self.session.execute(stmt)
            orm_embedding = result.scalar_one_or_none()
            return to_domain(orm_embedding) if orm_embedding else None
        except SQLAlchemyError as e:
            logger.error("Failed to get speaker embedding %s: %s", uuid, str(e))
            raise DatabaseOperationError(
                operation="get_speaker_embedding",
                reason=str(e),
                original_error=e,
                identifier=uuid,
            )

    async def get_by_task(self, task_uuid: str) -> list[DomainSpeakerEmbedding]:
        """
        Retrieve all speaker embeddings for a task.

        Args:
            task_uuid: The UUID of the originating task

        Returns:
            List of speaker embedding entities
        """
        try:
            stmt = select(ORMSpeakerEmbedding).where(
                ORMSpeakerEmbedding.task_uuid == task_uuid
            )
            result = await self.session.execute(stmt)
            return [to_domain(row) for row in result.scalars().all()]
        except SQLAlchemyError as e:
            logger.error("Failed to get embeddings for task %s: %s", task_uuid, str(e))
            raise DatabaseOperationError(
                operation="get_speaker_embeddings_by_task",
                reason=str(e),
                original_error=e,
                identifier=task_uuid,
            )

    async def list_all(
        self, limit: int = 100, offset: int = 0
    ) -> list[DomainSpeakerEmbedding]:
        """
        List speaker embeddings with pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of speaker embedding entities
        """
        try:
            stmt = (
                select(ORMSpeakerEmbedding)
                .order_by(ORMSpeakerEmbedding.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(stmt)
            return [to_domain(row) for row in result.scalars().all()]
        except SQLAlchemyError as e:
            logger.error("Failed to list speaker embeddings: %s", str(e))
            raise DatabaseOperationError(
                operation="list_speaker_embeddings",
                reason=str(e),
                original_error=e,
            )

    async def update(self, uuid: str, update_data: dict[str, Any]) -> bool:
        """
        Update a speaker embedding.

        Args:
            uuid: The UUID of the embedding to update
            update_data: Dictionary of fields to update

        Returns:
            True if the embedding was found and updated
        """
        try:
            stmt = select(ORMSpeakerEmbedding).where(ORMSpeakerEmbedding.uuid == uuid)
            result = await self.session.execute(stmt)
            orm_embedding = result.scalar_one_or_none()
            if orm_embedding is None:
                return False

            for key, value in update_data.items():
                if hasattr(orm_embedding, key):
                    setattr(orm_embedding, key, value)

            await self.session.commit()
            logger.info("Speaker embedding updated: %s", uuid)
            return True
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error("Failed to update speaker embedding %s: %s", uuid, str(e))
            raise DatabaseOperationError(
                operation="update_speaker_embedding",
                reason=str(e),
                original_error=e,
                identifier=uuid,
            )

    async def delete(self, uuid: str) -> bool:
        """
        Delete a speaker embedding by UUID.

        Args:
            uuid: The UUID of the embedding to delete

        Returns:
            True if the embedding was found and deleted
        """
        try:
            stmt = select(ORMSpeakerEmbedding).where(ORMSpeakerEmbedding.uuid == uuid)
            result = await self.session.execute(stmt)
            orm_embedding = result.scalar_one_or_none()
            if orm_embedding is None:
                return False

            await self.session.delete(orm_embedding)
            await self.session.commit()
            logger.info("Speaker embedding deleted: %s", uuid)
            return True
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error("Failed to delete speaker embedding %s: %s", uuid, str(e))
            raise DatabaseOperationError(
                operation="delete_speaker_embedding",
                reason=str(e),
                original_error=e,
                identifier=uuid,
            )

    async def delete_by_task(self, task_uuid: str) -> int:
        """
        Delete all speaker embeddings for a task.

        Args:
            task_uuid: The UUID of the task

        Returns:
            Number of embeddings deleted
        """
        try:
            stmt = delete(ORMSpeakerEmbedding).where(
                ORMSpeakerEmbedding.task_uuid == task_uuid
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            count: int = result.rowcount
            logger.info("Deleted %d speaker embeddings for task %s", count, task_uuid)
            return count
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(
                "Failed to delete embeddings for task %s: %s", task_uuid, str(e)
            )
            raise DatabaseOperationError(
                operation="delete_speaker_embeddings_by_task",
                reason=str(e),
                original_error=e,
                identifier=task_uuid,
            )


class SyncSQLAlchemySpeakerEmbeddingRepository:
    """
    Sync SQLAlchemy implementation for background task usage.

    Used in background threads where async is not available.
    """

    def __init__(self, session: Session) -> None:
        """
        Initialize the repository with a sync database session.

        Args:
            session: The SQLAlchemy sync Session
        """
        self.session = session

    def add_batch(self, embeddings: list[DomainSpeakerEmbedding]) -> list[str]:
        """
        Add multiple speaker embeddings in a single transaction.

        Args:
            embeddings: List of SpeakerEmbedding entities to store

        Returns:
            List of UUIDs of the created embeddings
        """
        try:
            uuids = []
            for embedding in embeddings:
                orm_embedding = to_orm(embedding)
                self.session.add(orm_embedding)
                uuids.append(embedding.uuid)
            self.session.commit()
            logger.info("Stored %d speaker embeddings", len(uuids))
            return uuids
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error("Failed to store speaker embeddings: %s", str(e))
            raise DatabaseOperationError(
                operation="add_batch_speaker_embeddings",
                reason=str(e),
                original_error=e,
            )

    def get_all(self) -> list[DomainSpeakerEmbedding]:
        """
        Retrieve all speaker embeddings (for similarity search).

        Returns:
            List of all speaker embedding entities
        """
        try:
            stmt = select(ORMSpeakerEmbedding)
            result = self.session.execute(stmt)
            return [to_domain(row) for row in result.scalars().all()]
        except SQLAlchemyError as e:
            logger.error("Failed to get all speaker embeddings: %s", str(e))
            raise DatabaseOperationError(
                operation="get_all_speaker_embeddings",
                reason=str(e),
                original_error=e,
            )
