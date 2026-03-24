"""Custom log formatters for structured and human-readable logging."""

import logging
from typing import Any

from pythonjsonlogger.json import JsonFormatter


class StructuredJsonFormatter(JsonFormatter):
    """JSON formatter for structured logging in production.

    Includes timestamp, level, logger name, message, request_id,
    user_id, and any extra fields. Enriches records with wide-event
    fields (duration_ms, status_code, endpoint) when available.
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

        # Add request-context fields injected by RequestContextFilter
        for field in (
            "request_id",
            "user_id",
            "ip_address",
            "endpoint",
            "duration_ms",
            "status_code",
        ):
            value = getattr(record, field, None)
            if value is not None:
                log_record[field] = value
