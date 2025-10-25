"""Request logging middleware for structured logging.

This middleware logs request start and response completion with
sanitization of sensitive headers.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.middleware.utils import get_client_ip, sanitize_headers
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request/response logging.

    This middleware:
    - Logs request start with method, path, and sanitized headers
    - Logs response completion with status code
    - Sanitizes sensitive headers (Authorization, cookies, etc.)
    - Handles exceptions and logs errors
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Any]]
    ) -> Response:
        """Log request start and response completion.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            Response object

        Raises:
            Exception: Re-raises any exception after logging
        """
        settings = get_settings()

        # Skip logging if disabled
        if not settings.middleware.ENABLE_REQUEST_LOGGING:
            return await call_next(request)  # type: ignore[no-any-return]

        # Log request start
        client_ip = get_client_ip(request)
        sanitized_headers = sanitize_headers(
            dict(request.headers), settings.middleware.SENSITIVE_HEADERS
        )

        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "client_ip": client_ip,
                "headers": sanitized_headers,
            },
        )

        try:
            # Process request
            response = await call_next(request)

            # Log response completion
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"(status: {response.status_code})",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )

            return response  # type: ignore[no-any-return]

        except Exception as e:
            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise
