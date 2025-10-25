"""Service for Voice Activity Detection using Silero VAD."""

from collections import deque
from typing import Any

import numpy as np
import torch

from app.api.schemas.websocket_schemas import VADConfig
from app.core.logging import logger


class SileroVADService:
    """Voice Activity Detection service using Silero VAD model."""

    def __init__(self, config: VADConfig, sample_rate: int = 16000) -> None:
        """
        Initialize Silero VAD service.

        Args:
            config: VAD configuration
            sample_rate: Audio sample rate in Hz
        """
        self.config = config
        self.sample_rate = sample_rate
        self.model: Any = None
        self.utils: Any = None
        self._is_speech = False
        self._speech_frames: deque[np.ndarray] = deque()
        self._pre_roll_buffer: deque[np.ndarray] = deque(
            maxlen=self._calculate_pre_roll_buffer_size()
        )
        self._current_speech_duration = 0.0
        self._silence_duration = 0.0

        logger.info("Initializing Silero VAD service with sample rate %d", sample_rate)
        self._load_model()

    def _calculate_pre_roll_buffer_size(self) -> int:
        """
        Calculate the size of the pre-roll buffer in frames.

        Returns:
            Number of frames to store in pre-roll buffer
        """
        # Calculate how many window_size chunks fit in pre_roll_buffer_ms
        pre_roll_samples = (self.config.pre_roll_buffer_ms * self.sample_rate) // 1000
        return max(1, pre_roll_samples // self.config.window_size_samples)

    def _load_model(self) -> None:
        """Load the Silero VAD model from torch.hub."""
        try:
            logger.info("Loading Silero VAD model from torch.hub")
            self.model, self.utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
            )
            logger.info("Silero VAD model loaded successfully")
        except Exception as e:
            logger.exception("Failed to load Silero VAD model: %s", str(e))
            raise RuntimeError(f"Failed to load Silero VAD model: {str(e)}") from e

    def process_audio_chunk(
        self, audio_chunk: np.ndarray
    ) -> tuple[bool, bool, np.ndarray | None]:
        """
        Process an audio chunk and detect speech.

        Args:
            audio_chunk: Audio data as numpy array (float32, range -1.0 to 1.0)

        Returns:
            Tuple of (is_speech, speech_ended, accumulated_audio)
            - is_speech: Whether current chunk contains speech
            - speech_ended: Whether speech segment has ended
            - accumulated_audio: Complete audio segment if speech ended, None otherwise
        """
        # Convert to torch tensor
        audio_tensor = torch.from_numpy(audio_chunk)

        # Get speech probability
        speech_prob = self.model(audio_tensor, self.sample_rate).item()

        is_currently_speech = speech_prob > self.config.threshold

        # Update pre-roll buffer (always, regardless of speech state)
        self._pre_roll_buffer.append(audio_chunk)

        speech_ended = False
        accumulated_audio = None

        if is_currently_speech:
            # Speech detected
            if not self._is_speech:
                # Speech started - add pre-roll buffer
                logger.debug(
                    "Speech started detected (prob: %.3f, threshold: %.3f)",
                    speech_prob,
                    self.config.threshold,
                )
                self._is_speech = True
                self._current_speech_duration = 0.0
                self._silence_duration = 0.0

                # Add pre-roll buffer to speech frames
                for buffered_chunk in self._pre_roll_buffer:
                    self._speech_frames.append(buffered_chunk)
            else:
                # Continue speech
                self._speech_frames.append(audio_chunk)

            # Update speech duration
            chunk_duration = len(audio_chunk) / self.sample_rate
            self._current_speech_duration += chunk_duration
            self._silence_duration = 0.0

        else:
            # No speech detected
            if self._is_speech:
                # Potential silence during speech
                self._speech_frames.append(audio_chunk)

                chunk_duration = len(audio_chunk) / self.sample_rate
                self._silence_duration += chunk_duration

                # Check if silence duration exceeds threshold
                min_silence_s = self.config.min_silence_duration_ms / 1000.0
                if self._silence_duration >= min_silence_s:
                    # Speech ended
                    logger.debug(
                        "Speech ended detected (duration: %.3fs, silence: %.3fs)",
                        self._current_speech_duration,
                        self._silence_duration,
                    )

                    # Check if utterance meets minimum length
                    if (
                        self._current_speech_duration
                        >= self.config.min_utterance_length_s
                    ):
                        # Combine all speech frames
                        accumulated_audio = np.concatenate(list(self._speech_frames))
                        speech_ended = True
                        logger.info(
                            "Valid utterance detected (duration: %.3fs)",
                            self._current_speech_duration,
                        )
                    else:
                        logger.debug(
                            "Utterance too short (%.3fs < %.3fs), discarding",
                            self._current_speech_duration,
                            self.config.min_utterance_length_s,
                        )

                    # Reset state
                    self._is_speech = False
                    self._speech_frames.clear()
                    self._current_speech_duration = 0.0
                    self._silence_duration = 0.0

        return (is_currently_speech, speech_ended, accumulated_audio)

    def reset(self) -> None:
        """Reset the VAD state."""
        logger.debug("Resetting VAD state")
        self._is_speech = False
        self._speech_frames.clear()
        self._pre_roll_buffer.clear()
        self._current_speech_duration = 0.0
        self._silence_duration = 0.0

    def get_current_speech_duration(self) -> float:
        """
        Get the current speech duration in seconds.

        Returns:
            Current speech duration in seconds
        """
        return self._current_speech_duration

    def is_speaking(self) -> bool:
        """
        Check if currently in a speech segment.

        Returns:
            True if currently in speech, False otherwise
        """
        return self._is_speech
