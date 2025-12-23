"""Timing middleware for request duration tracking.

This middleware measures the time taken to process each request and
logs slow requests that exceed a configurable threshold.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware to measure and log request duration.

    This middleware:
    - Records request start time
    - Calculates processing duration
    - Adds X-Response-Time header to response
    - Logs request timing with correlation ID
    - Logs warnings for slow requests
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Any]]
    ) -> Response:
        """Measure request processing time.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            Response with X-Response-Time header
        """
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time
        duration_ms = duration * 1000

        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Log timing
        logger.info(
            f"{request.method} {request.url.path} completed in {duration_ms:.2f}ms "
            f"(status: {response.status_code})"
        )

        # Log slow requests
        settings = get_settings()
        if duration > settings.middleware.SLOW_REQUEST_THRESHOLD:
            logger.warning(
                f"Slow request detected: {request.method} {request.url.path} "
                f"took {duration_ms:.2f}ms "
                f"(threshold: {settings.middleware.SLOW_REQUEST_THRESHOLD}s)"
            )

        return response  # type: ignore[no-any-return]
