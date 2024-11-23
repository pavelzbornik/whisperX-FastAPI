"""This module configures the central logging for the whisperX application."""

import logging
import logging.config
import os

import yaml

# Determine environment and set log level accordingly
from .config import Config

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

# Apply the updated logging configuration
logging.config.dictConfig(config)

# Save the updated config back to the YAML file
with open(config_path, "w") as f:
    yaml.dump(config, f)

# Configure whisperX logger
logger = logging.getLogger("whisperX")
logger.setLevel(log_level)

# Log environment variables
logger.info(f"Environment: {env}")
logger.info(f"Log level: {log_level}")
logger.debug(f"Debug messages enabled: {debug}")
