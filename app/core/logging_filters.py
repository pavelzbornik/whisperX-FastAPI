"""Logging filters for structured logging.

This module provides custom logging filters to inject request IDs
and other contextual information into log records.
"""

import logging
from contextvars import ContextVar

# Use same context variable name for consistency
# We don't import from middleware to avoid circular imports
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIDFilter(logging.Filter):
    """Add request ID to all log records.

    This filter injects the current request ID (from context variable)
    into each log record, enabling correlation of logs across the
    request lifecycle and background tasks.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Inject request_id into log record.

        Args:
            record: The log record to filter

        Returns:
            Always True (doesn't filter out records)
        """
        record.request_id = request_id_var.get() or "no-request-id"
        return True
