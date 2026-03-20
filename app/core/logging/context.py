"""Request-scoped context for structured logging via contextvars."""

import logging
from contextvars import ContextVar
from typing import Any

# Context variables set once per request by middleware
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
ip_address_var: ContextVar[str | None] = ContextVar("ip_address", default=None)
endpoint_var: ContextVar[str | None] = ContextVar("endpoint", default=None)


class RequestContextFilter(logging.Filter):
    """Inject request-scoped fields into every log record.

    Attach this filter to handlers so that ``request_id``, ``user_id``,
    ``ip_address``, and ``endpoint`` are available to formatters without
    the caller having to pass them explicitly.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Enrich *record* with current request context.

        Args:
            record: The log record to enrich.

        Returns:
            Always ``True`` — this filter never suppresses records.
        """
        request_id = request_id_var.get()
        if not hasattr(record, "request_id") or getattr(record, "request_id") is None:
            record.request_id = request_id

        user_id = user_id_var.get()
        if not hasattr(record, "user_id") or getattr(record, "user_id") is None:
            record.user_id = user_id

        ip_address = ip_address_var.get()
        if not hasattr(record, "ip_address") or getattr(record, "ip_address") is None:
            record.ip_address = ip_address

        endpoint = endpoint_var.get()
        if not hasattr(record, "endpoint") or getattr(record, "endpoint") is None:
            record.endpoint = endpoint
        return True


def get_request_context() -> dict[str, Any]:
    """Return the current request context as a dictionary.

    Useful for components (e.g. ``AuditLogger``) that need the context
    values without coupling to ``logging.LogRecord``.

    Returns:
        Dictionary with ``request_id``, ``user_id``, and ``ip_address``.
    """
    return {
        "request_id": request_id_var.get(),
        "user_id": user_id_var.get(),
        "ip_address": ip_address_var.get(),
    }
