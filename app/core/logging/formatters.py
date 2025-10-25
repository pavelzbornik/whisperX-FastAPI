"""Custom log formatters for structured and human-readable logging."""

import logging
from typing import Any

try:
    from pythonjsonlogger import jsonlogger
except ImportError:
    jsonlogger = None  # type: ignore[assignment]


class StructuredJsonFormatter(jsonlogger.JsonFormatter):  # type: ignore[misc, name-defined]
    """JSON formatter for structured logging in production.

    Includes timestamp, level, logger name, message, request_id,
    user_id, and any extra fields.
    """

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add custom fields to the JSON log record.

        Args:
            log_record: Dictionary containing the log record
            record: Standard Python LogRecord object
            message_dict: Dictionary of message fields
        """
        super().add_fields(log_record, record, message_dict)

        # Ensure timestamp is included
        if "timestamp" not in log_record:
            log_record["timestamp"] = self.formatTime(record, self.datefmt)

        # Ensure level is included
        if "level" not in log_record:
            log_record["level"] = record.levelname

        # Ensure logger name is included
        if "logger" not in log_record:
            log_record["logger"] = record.name

        # Add request_id if available
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id

        # Add user_id if available
        if hasattr(record, "user_id"):
            log_record["user_id"] = record.user_id


class HumanReadableFormatter(logging.Formatter):
    """Human-readable formatter for development environments.

    Provides colorized, easy-to-read log output for terminal display.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the human-readable formatter.

        Args:
            *args: Positional arguments for parent Formatter
            **kwargs: Keyword arguments for parent Formatter
        """
        super().__init__(*args, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record for human-readable output.

        Args:
            record: Standard Python LogRecord object

        Returns:
            Formatted log string
        """
        # Add request_id to the record if available
        if hasattr(record, "request_id"):
            request_id = f"[{record.request_id}] "
        else:
            request_id = ""

        # Create the formatted message
        formatted = super().format(record)

        # Insert request_id after the level name if present
        if request_id:
            parts = formatted.split(" - ", 2)
            if len(parts) >= 3:
                formatted = f"{parts[0]} - {parts[1]} - {request_id}{parts[2]}"

        return formatted
