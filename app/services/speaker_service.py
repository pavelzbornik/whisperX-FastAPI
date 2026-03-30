"""Service for managing speaker embeddings — CRUD, search, and identification."""

from uuid import uuid4

import numpy as np

from app.domain.entities.speaker_embedding import SpeakerEmbedding
from app.domain.repositories.speaker_embedding_repository import (
    ISpeakerEmbeddingRepository,
)


class SpeakerService:
    """Business logic for speaker embedding lifecycle."""

    def __init__(self, repository: ISpeakerEmbeddingRepository) -> None:
        """
        Initialize the speaker service.

        Args:
            repository: The speaker embedding repository
        """
        self.repository = repository

    async def create(
        self,
        speaker_label: str,
        embedding: list[float],
        description: str | None = None,
        task_uuid: str | None = None,
    ) -> str:
        """
        Create a new speaker embedding.

        Args:
            speaker_label: User-facing name for the speaker
            embedding: Speaker embedding vector
            description: Optional description
            task_uuid: Optional link to originating task

        Returns:
            UUID of the created speaker embedding
        """
        speaker = SpeakerEmbedding(
            uuid=str(uuid4()),
            speaker_label=speaker_label,
            embedding=embedding,
            description=description,
            task_uuid=task_uuid,
        )
        return await self.repository.add(speaker)

    async def get_by_id(self, uuid: str) -> SpeakerEmbedding | None:
        """
        Get a speaker embedding by UUID.

        Args:
            uuid: The unique identifier

        Returns:
            The speaker embedding, or None if not found
        """
        return await self.repository.get_by_id(uuid)

    async def get_by_task(self, task_uuid: str) -> list[SpeakerEmbedding]:
        """
        Get all speaker embeddings for a task.

        Args:
            task_uuid: The UUID of the originating task

        Returns:
            List of speaker embeddings
        """
        return await self.repository.get_by_task(task_uuid)

    async def list_all(
        self, limit: int = 100, offset: int = 0
    ) -> list[SpeakerEmbedding]:
        """
        List speaker embeddings with pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of speaker embeddings
        """
        return await self.repository.list_all(limit=limit, offset=offset)

    async def update(self, uuid: str, update_data: dict[str, object]) -> bool:
        """
        Update a speaker embedding.

        Args:
            uuid: The UUID of the embedding to update
            update_data: Fields to update (speaker_label, description, embedding)

        Returns:
            True if found and updated
        """
        return await self.repository.update(uuid, update_data)

    async def delete(self, uuid: str) -> bool:
        """
        Delete a speaker embedding.

        Args:
            uuid: The UUID to delete

        Returns:
            True if found and deleted
        """
        return await self.repository.delete(uuid)

    async def delete_by_task(self, task_uuid: str) -> int:
        """
        Delete all speaker embeddings for a task.

        Args:
            task_uuid: The task UUID

        Returns:
            Number of embeddings deleted
        """
        return await self.repository.delete_by_task(task_uuid)

    async def search_similar(
        self,
        embedding: list[float],
        limit: int = 5,
        threshold: float = 0.7,
    ) -> list[tuple[SpeakerEmbedding, float]]:
        """
        Search for similar speakers by cosine similarity.

        Args:
            embedding: Query embedding vector
            limit: Maximum number of results
            threshold: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of (speaker_embedding, similarity_score) tuples, sorted by similarity
        """
        all_embeddings = await self.repository.list_all(limit=10000, offset=0)
        if not all_embeddings:
            return []

        query = np.array(embedding, dtype=np.float64)
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return []

        results: list[tuple[SpeakerEmbedding, float]] = []
        for speaker in all_embeddings:
            vec = np.array(speaker.embedding, dtype=np.float64)
            vec_norm = np.linalg.norm(vec)
            if vec_norm == 0:
                continue
            similarity = float(np.dot(query, vec) / (query_norm * vec_norm))
            if similarity >= threshold:
                results.append((speaker, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    async def identify(
        self,
        embedding: list[float],
        threshold: float = 0.7,
    ) -> tuple[SpeakerEmbedding, float] | None:
        """
        Identify the best-matching speaker above threshold.

        Args:
            embedding: Query embedding vector
            threshold: Minimum similarity score

        Returns:
            Tuple of (best_match, similarity) or None if no match above threshold
        """
        matches = await self.search_similar(
            embedding=embedding, limit=1, threshold=threshold
        )
        if matches:
            return matches[0]
        return None
