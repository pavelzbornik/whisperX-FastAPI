"""WhisperX implementation of diarization service."""

import gc
from typing import Any

import numpy as np
import pandas as pd
import torch
from whisperx.diarize import DiarizationPipeline

from app.core.logging import logger


class WhisperXDiarizationService:
    """
    WhisperX/PyAnnote-based implementation of diarization service.

    This service wraps the WhisperX diarization pipeline (PyAnnote) to provide
    speaker diarization functionality following the IDiarizationService interface.
    """

    def __init__(self, hf_token: str) -> None:
        """
        Initialize the diarization service.

        Args:
            hf_token: HuggingFace authentication token for model access
        """
        self.hf_token = hf_token
        self.model: Any = None
        self.logger = logger

    def diarize(
        self,
        audio: np.ndarray[Any, np.dtype[np.float32]],
        device: str,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> pd.DataFrame:
        """
        Identify speakers using PyAnnote diarization model.

        Args:
            audio: Audio data as numpy array (float32)
            device: Device to use ('cpu' or 'cuda')
            min_speakers: Minimum number of speakers (optional)
            max_speakers: Maximum number of speakers (optional)

        Returns:
            DataFrame with speaker segments
        """
        self.logger.debug("Starting diarization with device: %s", device)

        # Log GPU memory before loading model
        if torch.cuda.is_available():
            self.logger.debug(
                f"GPU memory before loading model - used: {torch.cuda.memory_allocated() / 1024**2:.2f} MB, "
                f"available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
            )

        # Load model
        model = DiarizationPipeline(use_auth_token=self.hf_token, device=device)

        # Perform diarization
        result = model(
            audio=audio, min_speakers=min_speakers, max_speakers=max_speakers
        )

        # Log GPU memory before cleanup
        if torch.cuda.is_available():
            self.logger.debug(
                f"GPU memory before cleanup: {torch.cuda.memory_allocated() / 1024**2:.2f} MB, "
                f"available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
            )

        # Clean up model
        gc.collect()
        torch.cuda.empty_cache()
        del model

        # Log GPU memory after cleanup
        if torch.cuda.is_available():
            self.logger.debug(
                f"GPU memory after cleanup: {torch.cuda.memory_allocated() / 1024**2:.2f} MB, "
                f"available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
            )

        self.logger.debug("Completed diarization with device: %s", device)
        return result  # type: ignore[no-any-return]

    def load_model(self, device: str, hf_token: str) -> None:
        """
        Load diarization model.

        Args:
            device: Device to load model on ('cpu' or 'cuda')
            hf_token: HuggingFace authentication token
        """
        self.logger.info(f"Loading diarization model on {device}")
        self.hf_token = hf_token
        self.model = DiarizationPipeline(use_auth_token=self.hf_token, device=device)

    def unload_model(self) -> None:
        """Unload diarization model and free GPU memory."""
        if self.model:
            del self.model
            self.model = None
            gc.collect()
            torch.cuda.empty_cache()
            self.logger.debug("Diarization model unloaded and GPU memory cleared")
