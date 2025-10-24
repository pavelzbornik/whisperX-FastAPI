"""Interface for transcript alignment services using Protocol for structural typing."""

from typing import Any, Protocol

import numpy as np


class IAlignmentService(Protocol):
    """
    Interface for transcript alignment services.

    Implementations may use WhisperX alignment, forced alignment models, or
    other alignment techniques. This interface defines the contract for
    aligning transcripts to audio without tying the application to a
    specific implementation.

    The Protocol allows structural typing - any class implementing these methods
    with matching signatures will satisfy this interface.
    """

    def align(
        self,
        transcript: list[dict[str, Any]],
        audio: np.ndarray[Any, np.dtype[np.float32]],
        language_code: str,
        device: str,
        align_model: str | None = None,
        interpolate_method: str = "nearest",
        return_char_alignments: bool = False,
    ) -> dict[str, Any]:
        """
        Align transcript segments and words to precise audio timestamps.

        Args:
            transcript: List of transcript segments to align
            audio: Audio data as numpy array (float32)
            language_code: Language code of the transcript
            device: Device to use ('cpu' or 'cuda')
            align_model: Specific alignment model to use (optional)
            interpolate_method: Method for handling non-aligned words
            return_char_alignments: Whether to return character-level alignments

        Returns:
            Dictionary containing aligned transcript with:
                - segments: List of aligned segments with precise timestamps
                - word_segments: List of word-level alignments
                - Character alignments if requested
        """
        ...

    def load_model(
        self, language_code: str, device: str, model_name: str | None = None
    ) -> None:
        """
        Load alignment model for a specific language.

        Args:
            language_code: Language code for the alignment model
            device: Device to load model on ('cpu' or 'cuda')
            model_name: Specific model name to use (optional)
        """
        ...

    def unload_model(self) -> None:
        """
        Unload alignment model to free resources (GPU memory, etc.).

        This should properly clean up GPU memory using garbage collection
        and CUDA cache clearing if applicable.
        """
        ...
