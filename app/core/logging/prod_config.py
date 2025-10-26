"""Production environment logging configuration with JSON structured logging."""

import copy
import os
from typing import Any

from app.core.logging.base_config import get_base_config


def get_prod_config() -> dict[str, Any]:
    """Get production logging configuration with JSON output.

    Production configuration includes:
    - JSON structured logging for easy parsing and querying
    - INFO level for application loggers (less verbose)
    - Separate audit log handler with higher retention
    - File-based logging with rotation
    - Dedicated audit logger that never gets filtered

    Returns:
        Dictionary compatible with logging.config.dictConfig
    """
    config = copy.deepcopy(get_base_config())

    # Use JSON formatter for production
    config["formatters"]["json"] = {
        "()": "app.core.logging.formatters.StructuredJsonFormatter",
        "format": "%(timestamp)s %(level)s %(name)s %(message)s",
    }

    # Update handlers to use JSON formatter
    config["handlers"]["console"]["formatter"] = "json"
    config["handlers"]["error_console"]["formatter"] = "json"

    # Add file handler for application logs
    logs_dir = os.environ.get("LOGS_DIR", "logs")
    config["handlers"]["file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "level": "INFO",
        "formatter": "json",
        "filename": f"{logs_dir}/app.log",
        "maxBytes": 10485760,  # 10MB
        "backupCount": 5,
    }

    # Add audit log handler - separate file with longer retention
    config["handlers"]["audit"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "level": "INFO",
        "formatter": "json",
        "filename": f"{logs_dir}/audit.log",
        "maxBytes": 52428800,  # 50MB
        "backupCount": 10,  # Keep more audit logs for compliance
    }

    # Add file handler to app loggers
    config["loggers"]["app"]["handlers"] = ["console", "file"]
    config["loggers"]["whisperX"]["handlers"] = ["console", "file"]

    # Create audit logger
    config["loggers"]["audit"] = {
        "level": "INFO",
        "handlers": ["audit"],
        "propagate": False,
    }

    # Set INFO level for production (less verbose)
    config["loggers"]["app"]["level"] = "INFO"
    config["loggers"]["whisperX"]["level"] = "INFO"
    config["root"]["level"] = "INFO"

    return config
