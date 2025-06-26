"""This module configures the central logging for the whisperX application."""

import logging
import logging.config
import os
from typing import Optional

import yaml

from .request_context import get_correlation_id

# Determine environment and set log level accordingly
from .config import Config


class CorrelationIdFilter(logging.Filter):
    """Filter to add correlation ID to log records."""
    
    def filter(self, record):
        correlation_id = get_correlation_id()
        record.correlation_id = correlation_id if correlation_id else "no-correlation-id"
        return True


env = Config.ENVIRONMENT
log_level = Config.LOG_LEVEL

debug = env == "development"
log_level = os.getenv("LOG_LEVEL", "DEBUG" if debug else "INFO").upper()

# Load logging configuration from YAML file
config_path = os.path.join(os.path.dirname(__file__), "uvicorn_log_conf.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f.read())

# Update log levels based on environment variables
config["loggers"]["whisperX"]["level"] = log_level
config["loggers"]["uvicorn.error"]["level"] = log_level
config["loggers"]["uvicorn.access"]["level"] = log_level
config["root"]["level"] = log_level

# Update formatters to include correlation ID
for formatter_name, formatter_config in config.get("formatters", {}).items():
    if "format" in formatter_config:
        formatter_config["format"] = f"%(asctime)s - [%(correlation_id)s] - {formatter_config['format']}"

# Apply the updated logging configuration
logging.config.dictConfig(config)

# Add correlation ID filter to all handlers
correlation_filter = CorrelationIdFilter()
for handler in logging.root.handlers:
    handler.addFilter(correlation_filter)

# Save the updated config back to the YAML file
with open(config_path, "w") as f:
    yaml.dump(config, f)

# Configure whisperX logger
logger = logging.getLogger("whisperX")
logger.setLevel(log_level)
logger.addFilter(correlation_filter)

# Log environment variables
logger.info(f"Environment: {env}")
logger.info(f"Log level: {log_level}")
logger.debug(f"Debug messages enabled: {debug}")
