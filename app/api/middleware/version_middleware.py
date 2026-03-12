"""Middleware for API version detection and validation."""

import re
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class VersionMiddleware(BaseHTTPMiddleware):
    """Middleware for API version detection and validation.

    This middleware extracts and validates API versions from URL paths,
    ensuring only supported versions are accessed.
    """

    SUPPORTED_VERSIONS = {"v1"}
    VERSION_PATTERN = re.compile(r"/api/v(\d+)/")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Extract and validate API version from URL.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or handler in the chain.

        Returns:
            Response from the next handler.

        Raises:
            HTTPException: If an unsupported API version is requested.
        """
        path = request.url.path

        # Skip version check for unversioned endpoints
        if path.startswith("/health") or path == "/" or path.startswith("/docs"):
            return await call_next(request)

        # Extract version from path
        match = self.VERSION_PATTERN.search(path)
        if match:
            version = f"v{match.group(1)}"

            # Validate version - return error response instead of raising exception
            if version not in self.SUPPORTED_VERSIONS:
                return JSONResponse(
                    status_code=404,
                    content={"detail": f"API version {version} not found"},
                )

            # Add version to request state
            request.state.api_version = version

        return await call_next(request)
