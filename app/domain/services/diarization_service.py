"""Interface for speaker diarization services using Protocol for structural typing."""

from typing import Any, Protocol

import numpy as np

from app.domain.entities.diarization_result import DiarizationResult


class IDiarizationService(Protocol):
    """
    Interface for speaker diarization services.

    Implementations may use PyAnnote, other diarization models, or cloud services.
    This interface defines the contract for speaker diarization without tying
    the application to a specific implementation.

    The Protocol allows structural typing - any class implementing these methods
    with matching signatures will satisfy this interface.
    """

    def diarize(
        self,
        audio: np.ndarray[Any, np.dtype[np.float32]],
        device: str,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        return_embeddings: bool = False,
    ) -> DiarizationResult:
        """
        Identify speakers and their speaking segments in audio.

        Args:
            audio: Audio data as numpy array (float32)
            device: Device to use ('cpu' or 'cuda')
            min_speakers: Minimum number of speakers (optional)
            max_speakers: Maximum number of speakers (optional)
            return_embeddings: Whether to return speaker embedding vectors

        Returns:
            DiarizationResult containing speaker segments DataFrame and
            optionally speaker embeddings
        """
        ...

    def load_model(self, device: str, hf_token: str) -> None:
        """
        Load diarization model.

        Args:
            device: Device to load model on ('cpu' or 'cuda')
            hf_token: HuggingFace authentication token for model access
        """
        ...

    def unload_model(self) -> None:
        """
        Unload diarization model to free resources (GPU memory, etc.).

        This should properly clean up GPU memory using garbage collection
        and CUDA cache clearing if applicable.
        """
        ...
