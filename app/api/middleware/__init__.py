"""Middleware package for cross-cutting concerns.

This package provides middleware components for:
- Request ID generation and correlation
- Request/response timing
- Structured request/response logging
- Global error handling
"""

from app.api.middleware.error_handling import ErrorHandlingMiddleware
from app.api.middleware.request_id import RequestIDMiddleware, get_request_id
from app.api.middleware.request_logging import RequestLoggingMiddleware
from app.api.middleware.timing import TimingMiddleware

__all__ = [
    "RequestIDMiddleware",
    "TimingMiddleware",
    "RequestLoggingMiddleware",
    "ErrorHandlingMiddleware",
    "get_request_id",
]
