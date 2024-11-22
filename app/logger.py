"""This module configures the central logging for the whisperX application."""

import logging

# Configure central logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whisperX")
