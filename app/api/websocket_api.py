"""WebSocket API for real-time audio transcription."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.schemas.websocket_schemas import WebSocketSessionConfig
from app.core.logging import logger
from app.services.websocket_manager import WebSocketConnectionManager

# Create router for WebSocket endpoints
ws_router = APIRouter()

# Global connection manager instance
connection_manager = WebSocketConnectionManager()


@ws_router.websocket("/audio")
async def realtime_transcription_websocket(websocket: WebSocket) -> None:
    """
    Real-time audio transcription websocket endpoint.

    Accepts 16-bit PCM audio chunks and provides real-time transcription using
    WhisperX and Silero-VAD for voice activity detection.

    **Connection Flow:**
    1. Client connects to /audio WebSocket endpoint
    2. Server sends welcome message with session_id
    3. Client sends 16-bit PCM audio chunks (binary data)
    4. Server detects speech using Silero-VAD
    5. Server accumulates audio during speech
    6. On speech end (if >= 1.5s), server transcribes using WhisperX
    7. Server sends transcription result to client

    **Events sent to client:**
    - `proper_speech_start`: Speech detected (after VAD confirms)
    - `speech_false_detection`: Short speech detected (< 1.5s, discarded)
    - `speech_end`: Speech segment ended
    - `transcription`: Transcription result with text and metadata
    - `error`: Error occurred during processing
    - `info`: Informational messages

    **Audio Format:**
    - Encoding: 16-bit PCM (Little Endian)
    - Sample Rate: 16000 Hz
    - Channels: 1 (Mono)
    - Chunk Size: Flexible, recommended 512-2048 samples (32-128ms at 16kHz)

    **Configuration:**
    Default configuration uses:
    - VAD threshold: 0.5
    - Min utterance length: 1.5s
    - Pre-roll buffer: 300ms
    - Model: large-v3
    - Device: cuda (if available)

    Args:
        websocket: WebSocket connection
    """
    session_id: str | None = None

    try:
        # Use default configuration
        # In the future, this could be customized via query parameters
        config = WebSocketSessionConfig()

        # Accept connection and create session
        session_id = await connection_manager.connect(websocket, config)

        logger.info("Session %s: Real-time transcription started", session_id)

        # Main message loop
        while True:
            # Receive data from client
            data = await websocket.receive()

            session = connection_manager.get_session(session_id)
            if session is None:
                logger.warning(
                    "Session %s: Session not found, disconnecting", session_id
                )
                break

            # Handle binary audio data
            if "bytes" in data:
                audio_data = data["bytes"]
                await session.process_audio_data(audio_data)

            # Handle text messages (e.g., configuration updates)
            elif "text" in data:
                text_message = data["text"]
                await session.handle_text_message(text_message)

    except WebSocketDisconnect:
        logger.info(
            "Session %s: Client disconnected normally",
            session_id if session_id else "unknown",
        )
    except Exception as e:
        logger.exception(
            "Session %s: Error in WebSocket handler: %s",
            session_id if session_id else "unknown",
            str(e),
        )
    finally:
        # Clean up session
        if session_id:
            connection_manager.disconnect(session_id)
            logger.info("Session %s: Resources cleaned up", session_id)


@ws_router.get("/audio/sessions")
async def get_active_sessions() -> dict[str, int]:
    """
    Get the number of active WebSocket sessions.

    Returns:
        Dictionary with active session count
    """
    return {"active_sessions": connection_manager.get_active_session_count()}
