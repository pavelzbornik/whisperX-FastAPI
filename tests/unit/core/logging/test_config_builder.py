"""Tests for logging configuration builder."""

import logging
import os
from unittest.mock import patch


from app.core.logging.config_builder import configure_logging, get_logging_config


class TestGetLoggingConfig:
    """Test logging configuration selection."""

    def test_production_config(self) -> None:
        """Test that production config is selected for production environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = get_logging_config()

            # Check that JSON formatter is present (production uses JSON)
            assert "json" in config["formatters"]
            # Check that audit logger is configured
            assert "audit" in config["loggers"]
            # Check INFO level for production
            assert config["loggers"]["app"]["level"] == "INFO"

    def test_development_config(self) -> None:
        """Test that development config is selected for development environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            config = get_logging_config()

            # Check that colored formatter is present (dev uses colored)
            assert "colored" in config["formatters"]
            # Check DEBUG level for development
            assert config["loggers"]["app"]["level"] == "DEBUG"

    def test_testing_config(self) -> None:
        """Test that testing config is selected for testing environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "testing"}):
            config = get_logging_config()

            # Check WARNING level for testing (less noise)
            assert config["loggers"]["app"]["level"] == "WARNING"

    def test_default_to_production(self) -> None:
        """Test that unknown environments default to production config."""
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}):
            config = get_logging_config()

            # Should use production config for staging
            assert "json" in config["formatters"]
            assert "audit" in config["loggers"]

    def test_log_level_override(self) -> None:
        """Test that LOG_LEVEL environment variable overrides config."""
        with patch.dict(
            os.environ, {"ENVIRONMENT": "production", "LOG_LEVEL": "DEBUG"}
        ):
            config = get_logging_config()

            # LOG_LEVEL should override the default INFO level
            assert config["loggers"]["app"]["level"] == "DEBUG"
            assert config["loggers"]["whisperX"]["level"] == "DEBUG"
            assert config["root"]["level"] == "DEBUG"

    def test_environment_case_insensitive(self) -> None:
        """Test that environment name is case insensitive."""
        with patch.dict(os.environ, {"ENVIRONMENT": "PRODUCTION"}):
            config = get_logging_config()
            assert "json" in config["formatters"]

        with patch.dict(os.environ, {"ENVIRONMENT": "Development"}):
            config = get_logging_config()
            assert "colored" in config["formatters"]


class TestConfigureLogging:
    """Test logging configuration initialization."""

    def test_configure_logging_creates_logs_dir(self) -> None:
        """Test that configure_logging creates logs directory for production."""
        with patch.dict(
            os.environ, {"ENVIRONMENT": "production", "LOGS_DIR": "/tmp/test_logs"}
        ):
            with patch("os.makedirs") as mock_makedirs:
                with patch("logging.config.dictConfig"):
                    configure_logging()
                    mock_makedirs.assert_called_once_with(
                        "/tmp/test_logs", exist_ok=True
                    )

    def test_configure_logging_skips_logs_dir_for_dev(self) -> None:
        """Test that configure_logging doesn't create logs dir for development."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            with patch("os.makedirs") as mock_makedirs:
                with patch("logging.config.dictConfig"):
                    configure_logging()
                    # Should not create logs directory in development
                    mock_makedirs.assert_not_called()

    def test_configure_logging_applies_config(self) -> None:
        """Test that configure_logging applies the logging configuration."""
        with patch.dict(os.environ, {"ENVIRONMENT": "testing"}):
            with patch("logging.config.dictConfig") as mock_dictConfig:
                configure_logging()
                # Should call dictConfig with the configuration
                mock_dictConfig.assert_called_once()
                config = mock_dictConfig.call_args[0][0]
                assert "version" in config
                assert config["version"] == 1

    def test_configure_logging_logs_initialization(self) -> None:
        """Test that configure_logging logs initialization message."""
        with patch.dict(os.environ, {"ENVIRONMENT": "testing"}):
            # Reconfigure to capture log
            configure_logging()

            logger = logging.getLogger("app")
            with patch.object(logger, "info") as mock_info:
                configure_logging()
                # Should log the environment
                mock_info.assert_called()
