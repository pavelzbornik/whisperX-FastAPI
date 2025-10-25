"""This module configures the central logging for the whisperX application."""

import logging
import logging.config
import os

import yaml

# Determine environment and set log level accordingly
# Read directly from environment to avoid circular import with config module
env = os.getenv("ENVIRONMENT", "production").lower()
debug = env == "development"
log_level = os.getenv("LOG_LEVEL", "DEBUG" if debug else "INFO").upper()

# Load logging configuration from YAML file
# Navigate up to app directory to find the yaml file
config_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "uvicorn_log_conf.yaml"
)
with open(config_path, "r") as f:
    config = yaml.safe_load(f.read())

# Update log levels based on environment variables
config["loggers"]["whisperX"]["level"] = log_level
config["loggers"]["uvicorn.error"]["level"] = log_level
config["loggers"]["uvicorn.access"]["level"] = log_level
config["root"]["level"] = log_level

# Apply the updated logging configuration
logging.config.dictConfig(config)

# Add RequestIDFilter to all handlers programmatically
# This avoids circular import issues
from app.core.logging_filters import RequestIDFilter  # noqa: E402

request_id_filter = RequestIDFilter()
for handler in logging.root.handlers:
    handler.addFilter(request_id_filter)

# Configure whisperX logger
logger = logging.getLogger("whisperX")
logger.setLevel(log_level)

# Add filter to whisperX logger handlers
for handler in logger.handlers:
    handler.addFilter(request_id_filter)

# Log environment variables
logger.info(f"Environment: {env}")
logger.info(f"Log level: {log_level}")
logger.debug(f"Debug messages enabled: {debug}")
