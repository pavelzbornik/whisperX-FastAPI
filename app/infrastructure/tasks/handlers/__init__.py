"""Task handlers package for background task execution."""

from app.infrastructure.tasks.handlers.audio_processing_handler import (
    create_audio_processing_handler,
)

__all__ = ["create_audio_processing_handler"]
