"""ASGI middleware for request shaping, timing, and logging."""

import logging
import time
from collections.abc import Iterable, MutableMapping
from typing import Any

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_REDACTED = "***REDACTED***"

# Methods that can carry a request body worth size-checking.
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})


class MaxUploadSizeMiddleware:
    """Reject oversized uploads with HTTP 413 before the body is read.

    Enforced from the ``Content-Length`` header so the request body is never
    buffered to disk when it exceeds ``MAX_UPLOAD_SIZE_MB``. A cap of ``0``
    (the default) disables the check entirely, preserving prior behavior.
    Implemented as raw ASGI middleware so the response is produced without
    invoking the downstream application.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialise with the wrapped ASGI application.

        Args:
            app: The next ASGI application in the stack.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Reject oversized HTTP requests, otherwise defer to the inner app.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] != "http" or scope.get("method") not in _BODY_METHODS:
            await self.app(scope, receive, send)
            return

        max_mb = get_settings().MAX_UPLOAD_SIZE_MB
        if max_mb <= 0:
            await self.app(scope, receive, send)
            return

        max_bytes = max_mb * 1024 * 1024
        headers = dict(scope.get("headers", []))
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                content_length = int(raw_length)
            except ValueError:
                content_length = -1
            if content_length > max_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "message": (
                                "Upload exceeds the maximum allowed size of "
                                f"{max_mb} MB."
                            ),
                            "type": "invalid_request_error",
                            "code": "REQUEST_TOO_LARGE",
                        }
                    },
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


def _sanitize_query_string(raw_query: bytes, sensitive: set[str]) -> str:
    """Decode a query string, redacting the values of sensitive parameters.

    Credentials travel in query strings as well as headers — a bearer token, a
    pre-signed URL signature — and a log line is a durable place for one to end
    up. Parameter names are preserved so the shape of the request stays
    readable; only the values are masked.

    Args:
        raw_query: Raw ASGI ``query_string``.
        sensitive: Lowercase parameter names whose values must not be logged.

    Returns:
        The query string with sensitive values replaced.
    """
    decoded = raw_query.decode("latin-1")
    if not decoded:
        return ""

    sanitized = []
    for pair in decoded.split("&"):
        name, separator, _ = pair.partition("=")
        if separator and name.lower() in sensitive:
            sanitized.append(f"{name}={_REDACTED}")
        else:
            sanitized.append(pair)
    return "&".join(sanitized)


def _sanitize_headers(
    raw_headers: Iterable[tuple[bytes, bytes]], sensitive: set[str]
) -> dict[str, str]:
    """Decode request headers, redacting the sensitive ones.

    Args:
        raw_headers: ASGI ``(name, value)`` header pairs.
        sensitive: Lowercase header names whose values must not be logged.

    Returns:
        Mapping of header name to value, with sensitive values replaced.
    """
    sanitized = {}
    for raw_name, raw_value in raw_headers:
        name = raw_name.decode("latin-1").lower()
        if name in sensitive:
            sanitized[name] = _REDACTED
        else:
            sanitized[name] = raw_value.decode("latin-1")
    return sanitized


class TimingMiddleware:
    """Measure request duration, expose it, and warn about slow requests.

    Adds an ``X-Response-Time`` header to every HTTP response and logs a
    warning when a request takes longer than ``MIDDLEWARE__SLOW_REQUEST_THRESHOLD``
    seconds. Implemented as raw ASGI middleware for the same reason as
    ``RequestContextMiddleware``: ``BaseHTTPMiddleware`` introduces a task
    boundary that interferes with ``contextvars`` and background tasks.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialise with the wrapped ASGI application.

        Args:
            app: The next ASGI application in the stack.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Time the downstream request and annotate its response.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()

        async def send_with_timing(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                elapsed_ms = (time.perf_counter() - start) * 1000
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != b"x-response-time"
                ]
                headers.append((b"x-response-time", f"{elapsed_ms:.2f}ms".encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_timing)

        duration = time.perf_counter() - start
        threshold = get_settings().middleware.SLOW_REQUEST_THRESHOLD
        if duration > threshold:
            logger.warning(
                "Slow request: %s %s took %.2fms (threshold %.2fs)",
                scope.get("method", ""),
                scope.get("path", ""),
                duration * 1000,
                threshold,
            )


class RequestLoggingMiddleware:
    """Log request start and completion with sensitive headers redacted.

    Disabled by default; enable with ``MIDDLEWARE__ENABLE_REQUEST_LOGGING=true``.
    The client address is taken from the ASGI scope rather than from
    ``X-Forwarded-For``, which is caller-supplied and trivially spoofed.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialise with the wrapped ASGI application.

        Args:
            app: The next ASGI application in the stack.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Log the downstream request, then defer to the inner app.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        settings = get_settings()
        if scope["type"] != "http" or not settings.middleware.ENABLE_REQUEST_LOGGING:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        logger.info(
            "Request started: %s %s",
            method,
            path,
            extra={
                "method": method,
                "path": path,
                "query_params": _sanitize_query_string(
                    scope.get("query_string", b""),
                    settings.middleware.SENSITIVE_QUERY_PARAMS,
                ),
                "client_ip": client_ip,
                "headers": _sanitize_headers(
                    scope.get("headers", []), settings.middleware.SENSITIVE_HEADERS
                ),
            },
        )

        status_code: int | None = None

        async def send_capturing_status(message: MutableMapping[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_capturing_status)
        except Exception as exc:
            logger.error(
                "Request failed: %s %s",
                method,
                path,
                extra={"method": method, "path": path, "error": str(exc)},
                exc_info=True,
            )
            raise

        logger.info(
            "Request completed: %s %s (status: %s)",
            method,
            path,
            status_code,
            extra={"method": method, "path": path, "status_code": status_code},
        )
