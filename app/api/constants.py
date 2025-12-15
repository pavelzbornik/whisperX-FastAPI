"""API layer constants for endpoint responses and validations.

This module contains constants for API responses, error messages,
and file extensions used across API endpoints.
"""

# API Response messages
TASK_QUEUED_MESSAGE = "Task queued"
TASK_SCHEDULED_LOG_FORMAT = "Background task scheduled for processing: ID %s"

# Dependency injection error messages
CONTAINER_NOT_INITIALIZED_ERROR = (
    "Container not initialized. Call set_container() first."
)

# Schema field descriptions
AUDIO_LANGUAGE_DESCRIPTION = "Language of the audio"

# File extensions
JSON_EXTENSION = ".json"
