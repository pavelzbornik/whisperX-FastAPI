"""Testing environment logging configuration."""

import copy
from typing import Any

from app.core.logging.base_config import get_base_config


def get_test_config() -> dict[str, Any]:
    """Get testing logging configuration.

    Testing configuration includes:
    - Minimal console output to reduce noise
    - WARNING level for most loggers
    - In-memory logging (no file handlers)
    - Simplified formatters

    Returns:
        Dictionary compatible with logging.config.dictConfig
    """
    config = copy.deepcopy(get_base_config())

    # Set WARNING level for all loggers in tests to reduce noise
    config["loggers"]["app"]["level"] = "WARNING"
    config["loggers"]["whisperX"]["level"] = "WARNING"
    config["loggers"]["uvicorn"]["level"] = "ERROR"
    config["loggers"]["uvicorn.access"]["level"] = "ERROR"
    config["loggers"]["uvicorn.error"]["level"] = "ERROR"
    config["loggers"]["sqlalchemy.engine"]["level"] = "ERROR"

    # Root logger also at WARNING
    config["root"]["level"] = "WARNING"

    # Remove error_console handler in tests
    config["root"]["handlers"] = ["console"]

    return config
