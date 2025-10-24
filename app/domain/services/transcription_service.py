"""Interface for audio transcription services using Protocol for structural typing."""

from typing import Any, Protocol

import numpy as np


class ITranscriptionService(Protocol):
    """
    Interface for audio transcription services.

    Implementations may use WhisperX, OpenAI Whisper, or other providers.
    This interface defines the contract for transcription operations without
    tying the application to a specific ML library.

    The Protocol allows structural typing - any class implementing these methods
    with matching signatures will satisfy this interface.
    """

    def transcribe(
        self,
        audio: np.ndarray[Any, np.dtype[np.float32]],
        task: str,
        asr_options: dict[str, Any],
        vad_options: dict[str, Any],
        language: str,
        batch_size: int,
        chunk_size: int,
        model: str,
        device: str,
        device_index: int,
        compute_type: str,
        threads: int,
    ) -> dict[str, Any]:
        """
        Transcribe audio to text with segments and timestamps.

        Args:
            audio: Audio data as numpy array (float32)
            task: Transcription task type ('transcribe' or 'translate')
            asr_options: ASR model options
            vad_options: Voice Activity Detection options
            language: Language code for transcription
            batch_size: Batch size for processing
            chunk_size: Chunk size for processing
            model: Model name/size to use
            device: Device to use ('cpu' or 'cuda')
            device_index: Device index for multi-GPU setups
            compute_type: Computation precision ('float16', 'int8', etc.)
            threads: Number of threads to use

        Returns:
            Dictionary containing:
                - text: Full transcription text
                - segments: List of segment dictionaries with timestamps
                - language: Detected or specified language
        """
        ...

    def load_model(
        self,
        model_name: str,
        device: str,
        device_index: int,
        compute_type: str,
        asr_options: dict[str, Any],
        vad_options: dict[str, Any],
        language: str,
        task: str,
        threads: int,
    ) -> None:
        """
        Load ML model for transcription.

        Args:
            model_name: Name/size of the model to load
            device: Device to load model on ('cpu' or 'cuda')
            device_index: Device index for multi-GPU setups
            compute_type: Computation precision
            asr_options: ASR model options
            vad_options: Voice Activity Detection options
            language: Target language
            task: Task type
            threads: Number of threads to use
        """
        ...

    def unload_model(self) -> None:
        """
        Unload ML model to free resources (GPU memory, etc.).

        This should properly clean up GPU memory using garbage collection
        and CUDA cache clearing if applicable.
        """
        ...
