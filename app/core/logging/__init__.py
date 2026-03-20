"""Consolidated logging configuration and audit trail module.

This module provides:
- Environment-specific logging configuration (dev/staging/prod)
- Structured JSON logging for production
- Human-readable logging for development
- Audit logger for security-relevant events
- Request-scoped context injection via contextvars
"""

import logging

from app.core.logging.audit_logger import AuditLogger
from app.core.logging.config_builder import configure_logging, get_logging_config
from app.core.logging.context import RequestContextFilter, get_request_context

# Get the logger for backward compatibility
logger = logging.getLogger("whisperX")

__all__ = [
    "AuditLogger",
    "RequestContextFilter",
    "configure_logging",
    "get_logging_config",
    "get_request_context",
    "logger",
]
