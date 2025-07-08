"""Module for managing request context and correlation IDs."""

import uuid
from contextvars import ContextVar
from typing import Optional

# Context variables for request tracing
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
request_start_time_ctx: ContextVar[Optional[float]] = ContextVar('request_start_time', default=None)


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing."""
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID in the current context."""
    correlation_id_ctx.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Get the correlation ID from the current context."""
    return correlation_id_ctx.get()


def set_request_start_time(start_time: float) -> None:
    """Set the request start time in the current context."""
    request_start_time_ctx.set(start_time)


def get_request_start_time() -> Optional[float]:
    """Get the request start time from the current context."""
    return request_start_time_ctx.get()