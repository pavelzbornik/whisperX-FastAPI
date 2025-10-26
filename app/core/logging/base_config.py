"""Base logging configuration shared across all environments."""

from typing import Any


def get_base_config() -> dict[str, Any]:
    """Get base logging configuration shared across environments.

    This provides the foundation for all environment-specific configurations,
    including standard formatters, handlers, and logger hierarchy.

    Returns:
        Dictionary compatible with logging.config.dictConfig
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
            "error_console": {
                "class": "logging.StreamHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "app": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "whisperX": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "gunicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "gunicorn.error": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "gunicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "pytorch_lightning.utilities.migration": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "speechbrain.utils.quirks": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["console", "error_console"],
        },
    }
