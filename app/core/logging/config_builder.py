"""Dynamic logging configuration builder based on environment."""

import logging
import logging.config
import os
from typing import Any

from app.core.logging.dev_config import get_dev_config
from app.core.logging.prod_config import get_prod_config
from app.core.logging.test_config import get_test_config


def get_logging_config() -> dict[str, Any]:
    """Get logging configuration based on environment.

    Reads the ENVIRONMENT variable to determine which configuration to use:
    - production: JSON structured logging with file handlers
    - development: Colorized human-readable logging
    - testing: Minimal logging to reduce test noise

    Environment variables:
    - ENVIRONMENT: Environment name (default: production)
    - LOG_LEVEL: Override log level for app loggers

    Returns:
        Dictionary compatible with logging.config.dictConfig
    """
    environment = os.getenv("ENVIRONMENT", "production").lower()

    # Select configuration based on environment
    if environment == "testing":
        config = get_test_config()
    elif environment == "development":
        config = get_dev_config()
    else:
        # Default to production for staging, production, or unknown environments
        config = get_prod_config()

    # Allow LOG_LEVEL override via environment variable
    log_level = os.getenv("LOG_LEVEL")
    if log_level:
        log_level = log_level.upper()
        # Update app and whisperX loggers
        if "app" in config["loggers"]:
            config["loggers"]["app"]["level"] = log_level
        if "whisperX" in config["loggers"]:
            config["loggers"]["whisperX"]["level"] = log_level
        # Update root logger
        config["root"]["level"] = log_level

    return config


def configure_logging() -> None:
    """Configure logging for the application.

    This function should be called early in the application startup,
    before any logging occurs. It:
    1. Creates the logs directory if needed (for production)
    2. Loads the appropriate configuration
    3. Applies the configuration using dictConfig
    """
    # Create logs directory if it doesn't exist (for production)
    logs_dir = os.getenv("LOGS_DIR", "logs")
    environment = os.getenv("ENVIRONMENT", "production").lower()

    if environment == "production":
        os.makedirs(logs_dir, exist_ok=True)

    # Get and apply configuration
    config = get_logging_config()
    logging.config.dictConfig(config)

    # Get logger and log initialization
    logger = logging.getLogger("app")
    logger.info(
        "Logging configured for environment: %s",
        environment,
    )
