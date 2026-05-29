"""Unit tests for the settings configuration module."""

import os
from unittest.mock import patch

import pytest

from app.core.config import (
    AuthSettings,
    DatabaseSettings,
    LoggingSettings,
    RateLimitKeyStrategy,
    RateLimitSettings,
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
        # Save and remove HF_TOKEN from environment if set
        hf_token_backup = os.environ.pop("HF_TOKEN", None)
        try:
            settings = WhisperSettings()
            assert settings.WHISPER_MODEL == WhisperModel.tiny
            assert settings.DEFAULT_LANG == "en"
            assert settings.HF_TOKEN is None
        finally:
            # Restore HF_TOKEN if it was set
            if hf_token_backup is not None:
                os.environ["HF_TOKEN"] = hf_token_backup

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
        # Use patch.dict to ensure environment is clean for this test
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "DEV": "false",
                "DB_URL": "sqlite:///records.db",
                "DEVICE": "cpu",
                "COMPUTE_TYPE": "int8",
                "WHISPER_MODEL": "tiny",
                "DEFAULT_LANG": "en",
            },
            clear=False,
        ):
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


class TestMaxConcurrentGpuTasks:
    """Test MAX_CONCURRENT_GPU_TASKS setting."""

    def test_default_value_is_one(self) -> None:
        """Test that default MAX_CONCURRENT_GPU_TASKS is 1."""
        env = {
            "DEVICE": "cpu",
            "COMPUTE_TYPE": "int8",
            "DB_URL": os.environ.get("DB_URL", "sqlite:///records.db"),
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.MAX_CONCURRENT_GPU_TASKS == 1

    def test_env_var_override(self) -> None:
        """Test setting MAX_CONCURRENT_GPU_TASKS via environment variable."""
        env = {
            "DEVICE": "cpu",
            "COMPUTE_TYPE": "int8",
            "DB_URL": os.environ.get("DB_URL", "sqlite:///records.db"),
            "MAX_CONCURRENT_GPU_TASKS": "4",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.MAX_CONCURRENT_GPU_TASKS == 4

    def test_rejects_zero(self) -> None:
        """Test that MAX_CONCURRENT_GPU_TASKS rejects 0."""
        from pydantic import ValidationError as PydanticValidationError

        env = {
            "DEVICE": "cpu",
            "COMPUTE_TYPE": "int8",
            "DB_URL": os.environ.get("DB_URL", "sqlite:///records.db"),
            "MAX_CONCURRENT_GPU_TASKS": "0",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(PydanticValidationError):
                Settings()

    def test_rejects_negative(self) -> None:
        """Test that MAX_CONCURRENT_GPU_TASKS rejects negative values."""
        from pydantic import ValidationError as PydanticValidationError

        env = {
            "DEVICE": "cpu",
            "COMPUTE_TYPE": "int8",
            "DB_URL": os.environ.get("DB_URL", "sqlite:///records.db"),
            "MAX_CONCURRENT_GPU_TASKS": "-1",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(PydanticValidationError):
                Settings()


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


@pytest.mark.unit
class TestRateLimitSettings:
    """Test RateLimitSettings class."""

    def test_default_values_are_no_op(self) -> None:
        """Rate limiting is disabled by default with sensible budgets."""
        with patch.dict(os.environ, {}, clear=True):
            settings = RateLimitSettings()
            assert settings.ENABLED is False
            assert settings.REQUESTS_PER_MINUTE == 60
            assert settings.BURST == 10
            assert settings.KEY_STRATEGY == RateLimitKeyStrategy.ip

    def test_custom_values_via_env(self) -> None:
        """Values are read from RATE_LIMIT__ prefixed environment variables."""
        env = {
            "RATE_LIMIT__ENABLED": "true",
            "RATE_LIMIT__REQUESTS_PER_MINUTE": "5",
            "RATE_LIMIT__BURST": "2",
            "RATE_LIMIT__KEY_STRATEGY": "bearer_token",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = RateLimitSettings()
            assert settings.ENABLED is True
            assert settings.REQUESTS_PER_MINUTE == 5
            assert settings.BURST == 2
            assert settings.KEY_STRATEGY == RateLimitKeyStrategy.bearer_token

    def test_rejects_non_positive_rpm(self) -> None:
        """REQUESTS_PER_MINUTE must be >= 1."""
        from pydantic import ValidationError as PydanticValidationError

        with patch.dict(
            os.environ, {"RATE_LIMIT__REQUESTS_PER_MINUTE": "0"}, clear=True
        ):
            with pytest.raises(PydanticValidationError):
                RateLimitSettings()


@pytest.mark.unit
class TestAuthSettings:
    """Test AuthSettings class."""

    def test_default_values_are_no_op(self) -> None:
        """Authentication is disabled by default with no token."""
        with patch.dict(os.environ, {}, clear=True):
            settings = AuthSettings()
            assert settings.ENABLED is False
            assert settings.BEARER_TOKEN == ""

    def test_custom_values_via_env(self) -> None:
        """Values are read from AUTH__ prefixed environment variables."""
        env = {"AUTH__ENABLED": "true", "AUTH__BEARER_TOKEN": "secret"}
        with patch.dict(os.environ, env, clear=True):
            settings = AuthSettings()
            assert settings.ENABLED is True
            assert settings.BEARER_TOKEN == "secret"

    def test_enabled_requires_token(self) -> None:
        """Enabling auth without a token raises a validation error."""
        from pydantic import ValidationError as PydanticValidationError

        with patch.dict(os.environ, {"AUTH__ENABLED": "true"}, clear=True):
            with pytest.raises(PydanticValidationError):
                AuthSettings()


@pytest.mark.unit
class TestRequestShapingSettings:
    """Test request-shaping fields on the top-level Settings."""

    def test_defaults_are_no_op(self) -> None:
        """Upload cap and queue cap default to unlimited."""
        env = {"DEVICE": "cpu", "COMPUTE_TYPE": "int8"}
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.MAX_UPLOAD_SIZE_MB == 0
            assert settings.MAX_QUEUED_GPU_REQUESTS == 0
            assert settings.SYNC_GPU_QUOTA_FRACTION == 0.5

    def test_custom_values(self) -> None:
        """Request-shaping fields are read from the environment."""
        env = {
            "DEVICE": "cpu",
            "COMPUTE_TYPE": "int8",
            "MAX_UPLOAD_SIZE_MB": "25",
            "MAX_QUEUED_GPU_REQUESTS": "20",
            "SYNC_GPU_QUOTA_FRACTION": "0.25",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.MAX_UPLOAD_SIZE_MB == 25
            assert settings.MAX_QUEUED_GPU_REQUESTS == 20
            assert settings.SYNC_GPU_QUOTA_FRACTION == 0.25

    def test_fraction_out_of_range_rejected(self) -> None:
        """SYNC_GPU_QUOTA_FRACTION must be within [0, 1]."""
        from pydantic import ValidationError as PydanticValidationError

        env = {
            "DEVICE": "cpu",
            "COMPUTE_TYPE": "int8",
            "SYNC_GPU_QUOTA_FRACTION": "1.5",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(PydanticValidationError):
                Settings()

    def test_max_queued_gpu_requests_equal_to_one_rejected(self) -> None:
        """MAX_QUEUED_GPU_REQUESTS=1 cannot be split between paths."""
        from pydantic import ValidationError as PydanticValidationError

        env = {
            "DEVICE": "cpu",
            "COMPUTE_TYPE": "int8",
            "MAX_QUEUED_GPU_REQUESTS": "1",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(PydanticValidationError):
                Settings()
