"""Development environment logging configuration."""

import copy
from typing import Any

from app.core.logging.base_config import get_base_config


def get_dev_config() -> dict[str, Any]:
    """Get development logging configuration with readable output.

    Development configuration includes:
    - Colorized console output for better readability
    - DEBUG level for application loggers
    - More verbose SQLAlchemy logging for debugging
    - Human-readable format optimized for terminal display

    Returns:
        Dictionary compatible with logging.config.dictConfig
    """
    config = copy.deepcopy(get_base_config())

    # Use colorized formatter for development
    config["formatters"]["colored"] = {
        "()": "colorlog.ColoredFormatter",
        "format": "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "datefmt": "%H:%M:%S",
        "log_colors": {
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    }

    # Update console handler to use colored formatter
    config["handlers"]["console"]["formatter"] = "colored"

    # Set DEBUG level for app loggers in development
    config["loggers"]["app"]["level"] = "DEBUG"
    config["loggers"]["whisperX"]["level"] = "DEBUG"

    # Show SQL queries in development
    config["loggers"]["sqlalchemy.engine"]["level"] = "INFO"

    # More verbose uvicorn logging
    config["loggers"]["uvicorn"]["level"] = "DEBUG"
    config["loggers"]["uvicorn.error"]["level"] = "DEBUG"

    # Update root logger level
    config["root"]["level"] = "DEBUG"

    return config
