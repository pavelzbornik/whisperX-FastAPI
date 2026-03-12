"""Middleware for API version deprecation warnings."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class DeprecationMiddleware(BaseHTTPMiddleware):
    """Middleware for API version deprecation warnings.

    Adds RFC 8594 deprecation headers to responses for deprecated API versions.
    """

    # Deprecated versions configuration
    # Example when v1 is deprecated:
    # DEPRECATED_VERSIONS = {
    #     "v1": {
    #         "sunset": "2026-04-22",  # 6 months after deprecation
    #         "replacement": "v2",
    #         "docs_url": "https://api.example.com/docs/v2/"
    #     }
    # }
    DEPRECATED_VERSIONS: dict[str, dict[str, str]] = {}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Add deprecation headers for deprecated versions.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or handler in the chain.

        Returns:
            Response with deprecation headers if applicable.
        """
        response = await call_next(request)

        # Check if version is deprecated
        version = getattr(request.state, "api_version", None)
        if version and version in self.DEPRECATED_VERSIONS:
            info = self.DEPRECATED_VERSIONS[version]

            # Add RFC 8594 Deprecation header
            response.headers["Deprecation"] = "true"

            # Add Sunset header with end-of-life date
            response.headers["Sunset"] = info["sunset"]

            # Add Link header to new version docs
            docs_url = info.get("docs_url", f"/api/{info['replacement']}/docs")
            response.headers["Link"] = f'<{docs_url}>; rel="successor-version"'

        return response
