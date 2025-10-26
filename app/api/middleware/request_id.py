"""Request ID middleware for correlation tracking.

This middleware generates or extracts correlation IDs for request tracking
across the system and background tasks.
"""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Import shared context variable from logging_filters to avoid circular imports
from app.core.logging_filters import request_id_var


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to inject and propagate request correlation IDs.

    This middleware:
    - Checks for existing X-Request-ID header from client
    - Generates new UUID if not provided
    - Stores request ID in request state and context variable
    - Adds request ID to response headers
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Any]]
    ) -> Response:
        """Process request and inject correlation ID.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            Response with X-Request-ID header
        """
        # Check for existing request ID from client
        request_id = request.headers.get("X-Request-ID")

        # Generate new ID if not provided
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store in request state for access by handlers
        request.state.request_id = request_id

        # Store in context variable for logging
        request_id_var.set(request_id)

        # Process request
        response = await call_next(request)

        # Add to response headers
        response.headers["X-Request-ID"] = request_id

        return response  # type: ignore[no-any-return]


def get_request_id() -> str:
    """Get current request ID from context.

    Returns:
        The current request ID, or empty string if not set
    """
    return request_id_var.get()
