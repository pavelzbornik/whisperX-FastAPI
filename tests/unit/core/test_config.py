"""Unit tests for the settings configuration module."""

import os
from unittest.mock import patch


from app.core.config import (
    DatabaseSettings,
    LoggingSettings,
    Settings,
    WhisperSettings,
    get_settings,
)
from app.schemas import ComputeType, Device, WhisperModel


class TestDatabaseSettings:
    """Test DatabaseSettings class."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        # Save and remove DB_URL from environment if set
        db_url_backup = os.environ.pop("DB_URL", None)
        try:
            settings = DatabaseSettings()
            assert settings.DB_URL == "sqlite:///records.db"
            assert settings.DB_ECHO is False
        finally:
            # Restore DB_URL if it was set
            if db_url_backup is not None:
                os.environ["DB_URL"] = db_url_backup

    def test_custom_values(self) -> None:
        """Test setting custom values via environment variables."""
        with patch.dict(
            os.environ,
            {"DB_URL": "postgresql://localhost/test", "DB_ECHO": "true"},
        ):
            settings = DatabaseSettings()
            assert settings.DB_URL == "postgresql://localhost/test"
            assert settings.DB_ECHO is True


class TestWhisperSettings:
    """Test WhisperSettings class."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        settings = WhisperSettings()
        assert settings.WHISPER_MODEL == WhisperModel.tiny
        assert settings.DEFAULT_LANG == "en"
        assert settings.HF_TOKEN is None

    def test_device_auto_detection(self) -> None:
        """Test that device is auto-detected based on CUDA availability."""
        settings = WhisperSettings()
        # Device should be set based on torch.cuda.is_available()
        assert settings.DEVICE in [Device.cuda, Device.cpu]

    def test_compute_type_auto_correction_for_cpu(self) -> None:
        """Test that compute type is auto-corrected to int8 for CPU device."""
        with patch.dict(
            os.environ,
            {"DEVICE": "cpu", "COMPUTE_TYPE": "float16"},
        ):
            settings = WhisperSettings()
            assert settings.DEVICE == Device.cpu
            # Should auto-correct to int8
            assert settings.COMPUTE_TYPE == ComputeType.int8

    def test_compute_type_for_cuda(self) -> None:
        """Test compute type setting for CUDA device."""
        with patch.dict(
            os.environ,
            {"DEVICE": "cuda", "COMPUTE_TYPE": "float16"},
        ):
            settings = WhisperSettings()
            assert settings.DEVICE == Device.cuda
            assert settings.COMPUTE_TYPE == ComputeType.float16

    def test_allowed_extensions_computed_field(self) -> None:
        """Test that ALLOWED_EXTENSIONS is computed from audio and video extensions."""
        settings = WhisperSettings()
        assert settings.ALLOWED_EXTENSIONS == (
            settings.AUDIO_EXTENSIONS | settings.VIDEO_EXTENSIONS
        )
        # Verify some known extensions
        assert ".mp3" in settings.ALLOWED_EXTENSIONS
        assert ".mp4" in settings.ALLOWED_EXTENSIONS


class TestLoggingSettings:
    """Test LoggingSettings class."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        settings = LoggingSettings()
        assert settings.LOG_LEVEL == "INFO"
        assert settings.LOG_FORMAT == "text"
        assert settings.FILTER_WARNING is True

    def test_custom_values(self) -> None:
        """Test setting custom values."""
        with patch.dict(
            os.environ,
            {"LOG_LEVEL": "DEBUG", "LOG_FORMAT": "json", "FILTER_WARNING": "false"},
        ):
            settings = LoggingSettings()
            assert settings.LOG_LEVEL == "DEBUG"
            assert settings.LOG_FORMAT == "json"
            assert settings.FILTER_WARNING is False


class TestSettings:
    """Test main Settings class."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        settings = Settings()
        assert settings.ENVIRONMENT == "production"
        assert settings.DEV is False
        assert isinstance(settings.database, DatabaseSettings)
        assert isinstance(settings.whisper, WhisperSettings)
        assert isinstance(settings.logging, LoggingSettings)

    def test_environment_normalization(self) -> None:
        """Test that environment value is normalized to lowercase."""
        with patch.dict(os.environ, {"ENVIRONMENT": "DEVELOPMENT"}):
            settings = Settings()
            assert settings.ENVIRONMENT == "development"

    def test_nested_settings_access(self) -> None:
        """Test accessing nested settings."""
        # Just check the values from the test environment
        settings = Settings()
        # In test env, DB_URL is set by conftest
        assert settings.database.DB_URL  # Non-empty
        assert settings.whisper.WHISPER_MODEL == WhisperModel.tiny
        assert settings.logging.LOG_LEVEL == "INFO"

    def test_custom_nested_values(self) -> None:
        """Test setting custom nested values via environment variables."""
        with patch.dict(
            os.environ,
            {
                "DB_URL": "postgresql://test",
                "WHISPER_MODEL": "base",
                "LOG_LEVEL": "DEBUG",
            },
        ):
            settings = Settings()
            assert settings.database.DB_URL == "postgresql://test"
            assert settings.whisper.WHISPER_MODEL == WhisperModel.base
            assert settings.logging.LOG_LEVEL == "DEBUG"


class TestGetSettings:
    """Test get_settings singleton function."""

    def test_singleton_pattern(self) -> None:
        """Test that get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_settings_instance(self) -> None:
        """Test that get_settings returns a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)
