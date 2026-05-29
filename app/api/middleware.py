"""ASGI middleware for request shaping (upload size cap)."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings

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
