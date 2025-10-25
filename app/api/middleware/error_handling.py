"""Error handling middleware for global exception handling.

This middleware catches unhandled exceptions and returns consistent
error responses with correlation IDs.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.middleware.request_id import get_request_id
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Global exception handler for unhandled errors.

    This middleware:
    - Catches all unhandled exceptions
    - Logs errors with correlation ID
    - Returns consistent error response format
    - Includes correlation ID in error response
    - Prevents stack trace leakage in production
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Any]]
    ) -> JSONResponse:
        """Catch and handle unhandled exceptions.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            Either the normal response or an error response
        """
        try:
            return await call_next(request)  # type: ignore[no-any-return]
        except Exception as e:
            request_id = get_request_id()

            # Log error with correlation ID
            logger.error(
                f"Unhandled exception: {type(e).__name__}: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True,
            )

            # Build error response
            settings = get_settings()
            error_detail: dict[str, str] = {
                "message": "Internal server error",
                "request_id": request_id,
            }

            # Include details in development
            if settings.ENVIRONMENT == "development":
                error_detail["error"] = str(e)
                error_detail["type"] = type(e).__name__

            return JSONResponse(status_code=500, content=error_detail)
