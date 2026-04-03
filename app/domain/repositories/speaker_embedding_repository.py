"""Interface for speaker embedding repositories using Protocol for structural typing."""

from typing import Protocol

from app.domain.entities.speaker_embedding import SpeakerEmbedding


class ISpeakerEmbeddingRepository(Protocol):
    """
    Interface for speaker embedding persistence.

    Defines the contract for CRUD operations on speaker embeddings.
    Implementations may use SQLAlchemy, in-memory storage, or other backends.
    """

    async def add(self, embedding: SpeakerEmbedding) -> str:
        """
        Persist a speaker embedding.

        Args:
            embedding: The speaker embedding entity to store

        Returns:
            The UUID of the created embedding
        """
        ...

    async def get_by_id(self, uuid: str) -> SpeakerEmbedding | None:
        """
        Retrieve a speaker embedding by UUID.

        Args:
            uuid: The unique identifier of the embedding

        Returns:
            The speaker embedding entity, or None if not found
        """
        ...

    async def get_by_task(self, task_uuid: str) -> list[SpeakerEmbedding]:
        """
        Retrieve all speaker embeddings associated with a task.

        Args:
            task_uuid: The UUID of the originating task

        Returns:
            List of speaker embedding entities
        """
        ...

    async def list_all(
        self, limit: int = 100, offset: int = 0
    ) -> list[SpeakerEmbedding]:
        """
        List speaker embeddings with pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of speaker embedding entities
        """
        ...

    async def update(self, uuid: str, update_data: dict[str, object]) -> bool:
        """
        Update a speaker embedding.

        Args:
            uuid: The UUID of the embedding to update
            update_data: Dictionary of fields to update

        Returns:
            True if the embedding was found and updated
        """
        ...

    async def delete(self, uuid: str) -> bool:
        """
        Delete a speaker embedding by UUID.

        Args:
            uuid: The UUID of the embedding to delete

        Returns:
            True if the embedding was found and deleted
        """
        ...

    async def delete_by_task(self, task_uuid: str) -> int:
        """
        Delete all speaker embeddings associated with a task.

        Args:
            task_uuid: The UUID of the task

        Returns:
            Number of embeddings deleted
        """
        ...
