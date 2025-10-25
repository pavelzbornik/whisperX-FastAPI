"""This module configures the central logging for the whisperX application.

This module has been updated to use the consolidated logging configuration
from app.core.logging package. The configuration is now:
- Environment-specific (dev/staging/prod/test)
- Uses structured JSON logging in production
- Uses human-readable colored logging in development
- Supports audit logging for security-relevant events
"""

import logging

from app.core.logging.config_builder import configure_logging

# Configure logging using the new consolidated configuration
configure_logging()

# Get the logger for backward compatibility
logger = logging.getLogger("whisperX")
