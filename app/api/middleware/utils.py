"""Utility functions for middleware.

This module provides helper functions for middleware operations like
sanitizing sensitive data and extracting client information.
"""

from typing import Any

from starlette.requests import Request


def sanitize_headers(headers: dict[str, Any], sensitive: set[str]) -> dict[str, Any]:
    """Remove sensitive headers from log output.

    Args:
        headers: Dictionary of headers to sanitize
        sensitive: Set of header names to redact (case-insensitive)

    Returns:
        Dictionary with sensitive values replaced by ***REDACTED***
    """
    return {
        key: "***REDACTED***" if key.lower() in sensitive else value
        for key, value in headers.items()
    }


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxies.

    This function checks multiple headers to find the real client IP:
    1. X-Forwarded-For (from proxy/load balancer)
    2. X-Real-IP (from nginx)
    3. Direct client connection

    Args:
        request: The incoming HTTP request

    Returns:
        The client IP address or "unknown" if not available
    """
    # Check X-Forwarded-For header (proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP from the comma-separated list
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP header (nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to direct client
    return request.client.host if request.client else "unknown"
