"""WebSocket session manager for real-time transcription."""

import asyncio
import time
from typing import Any
from uuid import uuid4

import numpy as np
from fastapi import WebSocket

from app.api.schemas.websocket_schemas import (
    TranscriptionResult,
    WebSocketEventType,
    WebSocketMessage,
    WebSocketSessionConfig,
)
from app.core.config import Config
from app.core.logging import logger
from app.services.vad_service import SileroVADService
from app.services.whisperx_wrapper_service import transcribe_with_whisper


class WebSocketSessionManager:
    """Manages a WebSocket session for real-time transcription."""

    def __init__(
        self, websocket: WebSocket, config: WebSocketSessionConfig, session_id: str
    ) -> None:
        """
        Initialize WebSocket session manager.

        Args:
            websocket: WebSocket connection
            config: Session configuration
            session_id: Unique session identifier
        """
        self.websocket = websocket
        self.config = config
        self.session_id = session_id
        self.vad_service = SileroVADService(
            config.vad_config, config.audio_config.sample_rate
        )
        self.is_active = True
        self._speech_detected_notified = False

        logger.info("WebSocket session %s initialized", session_id)

    async def send_event(
        self, event_type: WebSocketEventType, data: dict[str, Any] | None = None
    ) -> None:
        """
        Send an event to the client.

        Args:
            event_type: Type of event to send
            data: Optional event data
        """
        message = WebSocketMessage(
            event=event_type, data=data or {}, timestamp=time.time()
        )
        try:
            await self.websocket.send_json(message.model_dump())
            logger.debug("Session %s: Sent event %s", self.session_id, event_type.value)
        except Exception as e:
            logger.exception(
                "Session %s: Failed to send event %s: %s",
                self.session_id,
                event_type.value,
                str(e),
            )
            raise

    async def process_audio_data(self, audio_data: bytes) -> None:
        """
        Process incoming audio data.

        Args:
            audio_data: Raw audio bytes (16-bit PCM)
        """
        try:
            # Convert bytes to numpy array (int16)
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)

            # Convert to float32 in range [-1.0, 1.0]
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            # Process with VAD
            is_speech, speech_ended, accumulated_audio = (
                self.vad_service.process_audio_chunk(audio_float32)
            )

            # Handle speech detection events
            if is_speech and not self._speech_detected_notified:
                # First proper speech detection
                self._speech_detected_notified = True
                await self.send_event(
                    WebSocketEventType.PROPER_SPEECH_START,
                    {"duration": self.vad_service.get_current_speech_duration()},
                )
                logger.info("Session %s: Proper speech started", self.session_id)

            elif not is_speech and self._speech_detected_notified:
                # False detection or speech ended
                if not speech_ended:
                    # Was a false detection (too short)
                    self._speech_detected_notified = False
                    await self.send_event(
                        WebSocketEventType.SPEECH_FALSE_DETECTION,
                        {"reason": "utterance_too_short"},
                    )
                    logger.info(
                        "Session %s: False speech detection (too short)",
                        self.session_id,
                    )

            # Handle speech end and transcription
            if speech_ended and accumulated_audio is not None:
                logger.info(
                    "Session %s: Speech ended, starting transcription (%.3fs)",
                    self.session_id,
                    len(accumulated_audio) / self.config.audio_config.sample_rate,
                )

                # Notify client that speech ended
                await self.send_event(
                    WebSocketEventType.SPEECH_END,
                    {
                        "duration": len(accumulated_audio)
                        / self.config.audio_config.sample_rate
                    },
                )

                # Reset speech detection flag
                self._speech_detected_notified = False

                # Perform transcription in background
                asyncio.create_task(self._transcribe_audio(accumulated_audio))

        except Exception as e:
            logger.exception(
                "Session %s: Error processing audio data: %s", self.session_id, str(e)
            )
            await self.send_event(
                WebSocketEventType.ERROR,
                {"message": f"Error processing audio: {str(e)}"},
            )

    async def _transcribe_audio(self, audio: np.ndarray) -> None:
        """
        Transcribe audio segment using WhisperX.

        Args:
            audio: Audio data as numpy array
        """
        try:
            logger.info("Session %s: Starting transcription", self.session_id)
            start_time = time.time()

            # Prepare transcription parameters
            language = self.config.transcription_config.language or Config.LANG
            model = self.config.transcription_config.model or Config.WHISPER_MODEL.value
            device = self.config.transcription_config.device or Config.DEVICE.value
            compute_type = (
                self.config.transcription_config.compute_type
                or Config.COMPUTE_TYPE.value
            )

            # Run transcription in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: transcribe_with_whisper(
                    audio=audio,
                    task="transcribe",
                    asr_options={},
                    vad_options={},
                    language=language,
                    batch_size=self.config.transcription_config.batch_size,
                    chunk_size=20,
                    model=model,  # type: ignore[arg-type]
                    device=device,  # type: ignore[arg-type]
                    device_index=0,
                    compute_type=compute_type,  # type: ignore[arg-type]
                    threads=0,
                ),
            )

            duration = time.time() - start_time
            logger.info(
                "Session %s: Transcription completed in %.3fs",
                self.session_id,
                duration,
            )

            # Extract text from segments
            text = " ".join(
                segment.get("text", "") for segment in result.get("segments", [])
            ).strip()

            # Send transcription result
            transcription_result = TranscriptionResult(
                text=text,
                language=result.get("language"),
                duration=duration,
                segments=result.get("segments"),
            )

            await self.send_event(
                WebSocketEventType.TRANSCRIPTION,
                transcription_result.model_dump(),
            )

            logger.info(
                "Session %s: Transcription sent to client: %s",
                self.session_id,
                text[:100],
            )

        except Exception as e:
            logger.exception(
                "Session %s: Transcription failed: %s", self.session_id, str(e)
            )
            await self.send_event(
                WebSocketEventType.ERROR,
                {"message": f"Transcription failed: {str(e)}"},
            )

    async def handle_text_message(self, message: str) -> None:
        """
        Handle text message from client (e.g., configuration updates).

        Args:
            message: Text message from client
        """
        logger.debug("Session %s: Received text message: %s", self.session_id, message)
        # For now, just acknowledge
        await self.send_event(
            WebSocketEventType.INFO, {"message": "Text message received"}
        )

    def cleanup(self) -> None:
        """Clean up session resources."""
        logger.info("Session %s: Cleaning up resources", self.session_id)
        self.is_active = False
        self.vad_service.reset()


class WebSocketConnectionManager:
    """Manages multiple WebSocket connections."""

    def __init__(self) -> None:
        """Initialize connection manager."""
        self.active_sessions: dict[str, WebSocketSessionManager] = {}
        logger.info("WebSocket connection manager initialized")

    async def connect(
        self, websocket: WebSocket, config: WebSocketSessionConfig
    ) -> str:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: WebSocket connection
            config: Session configuration

        Returns:
            Session ID
        """
        await websocket.accept()
        session_id = str(uuid4())

        session = WebSocketSessionManager(websocket, config, session_id)
        self.active_sessions[session_id] = session

        logger.info("Session %s: Connection established", session_id)

        # Send welcome message
        await session.send_event(
            WebSocketEventType.INFO,
            {
                "message": "Connected to real-time transcription service",
                "session_id": session_id,
            },
        )

        return session_id

    def disconnect(self, session_id: str) -> None:
        """
        Disconnect a WebSocket session.

        Args:
            session_id: Session identifier
        """
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.cleanup()
            del self.active_sessions[session_id]
            logger.info("Session %s: Disconnected", session_id)

    def get_session(self, session_id: str) -> WebSocketSessionManager | None:
        """
        Get a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session manager or None if not found
        """
        return self.active_sessions.get(session_id)

    def get_active_session_count(self) -> int:
        """
        Get the number of active sessions.

        Returns:
            Number of active sessions
        """
        return len(self.active_sessions)
