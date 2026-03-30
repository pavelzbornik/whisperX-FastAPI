"""Configuration module for the WhisperX FastAPI application."""

from functools import lru_cache
from typing import Optional

import torch
from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas import ComputeType, Device, WhisperModel


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    DB_URL: str = Field(
        default="sqlite:///records.db",
        description="Database connection URL",
    )
    DB_ECHO: bool = Field(
        default=False,
        description="Echo SQL queries for debugging",
    )


class WhisperSettings(BaseSettings):
    """WhisperX ML model configuration settings."""

    HF_TOKEN: Optional[str] = Field(
        default=None,
        description="HuggingFace API token for model downloads",
    )
    WHISPER_MODEL: WhisperModel = Field(
        default=WhisperModel.tiny,
        description="Whisper model size to use",
    )
    DEFAULT_LANG: str = Field(
        default="en",
        description="Default language for transcription",
    )
    DEVICE: Device = Field(
        default_factory=lambda: (
            Device.cuda if torch.cuda.is_available() else Device.cpu
        ),
        description="Device to use for computation (cuda or cpu)",
    )
    COMPUTE_TYPE: ComputeType = Field(
        default_factory=lambda: (
            ComputeType.float16 if torch.cuda.is_available() else ComputeType.int8
        ),
        description="Compute type for model inference",
    )

    AUDIO_EXTENSIONS: set[str] = {
        ".mp3",
        ".wav",
        ".awb",
        ".aac",
        ".ogg",
        ".oga",
        ".m4a",
        ".wma",
        ".amr",
    }
    VIDEO_EXTENSIONS: set[str] = {".mp4", ".mov", ".avi", ".wmv", ".mkv"}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ALLOWED_EXTENSIONS(self) -> set[str]:
        """Compute allowed extensions by combining audio and video."""
        return self.AUDIO_EXTENSIONS | self.VIDEO_EXTENSIONS

    @model_validator(mode="after")
    def validate_compute_type_for_cpu(self) -> "WhisperSettings":
        """Validate that CPU device uses int8 compute type."""
        if self.DEVICE == Device.cpu and self.COMPUTE_TYPE != ComputeType.int8:
            # Auto-correct instead of raising error
            self.COMPUTE_TYPE = ComputeType.int8
        return self


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    LOG_FORMAT: str = Field(
        default="text",
        description="Log format: text or json",
    )
    FILTER_WARNING: bool = Field(
        default=True,
        description="Filter specific warnings",
    )


class CallbackSettings(BaseSettings):
    """Callback configuration settings."""

    CALLBACK_TIMEOUT: int = Field(
        default=10,
        description="Timeout for callback requests in seconds",
    )
    CALLBACK_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum number of retries for failed callback requests",
    )


class SsrfSettings(BaseSettings):
    """SSRF protection configuration settings.

    Controls URL validation for outbound HTTP requests to prevent
    Server-Side Request Forgery attacks.

    Each option is configurable via an environment variable matching the
    field name, for example:
    - ``SSRF_PROTECTION_ENABLED``
    - ``SSRF_ALLOWED_SCHEMES``
    - ``SSRF_BLOCKED_NETWORKS``
    """

    SSRF_PROTECTION_ENABLED: bool = Field(
        default=True,
        description="Enable SSRF protection for outbound HTTP requests",
    )
    SSRF_ALLOWED_SCHEMES: list[str] = Field(
        default=["http", "https"],
        description="URL schemes permitted for outbound requests",
    )
    SSRF_BLOCKED_NETWORKS: list[str] = Field(
        default=[
            "0.0.0.0/8",
            "10.0.0.0/8",
            "100.64.0.0/10",
            "127.0.0.0/8",
            "169.254.0.0/16",
            "172.16.0.0/12",
            "192.0.0.0/24",
            "192.0.2.0/24",
            "192.88.99.0/24",
            "192.168.0.0/16",
            "198.18.0.0/15",
            "198.51.100.0/24",
            "203.0.113.0/24",
            "224.0.0.0/4",
            "240.0.0.0/4",
            "255.255.255.255/32",
            "::1/128",
            "fc00::/7",
            "fe80::/10",
        ],
        description="CIDR ranges blocked for outbound requests",
    )


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        env_nested_delimiter="__",
    )

    ENVIRONMENT: str = Field(
        default="production",
        description="Environment: development, testing, production",
    )
    DEV: bool = Field(
        default=False,
        description="Development mode flag",
    )
    MAX_CONCURRENT_GPU_TASKS: int = Field(
        default=1,
        ge=1,
        description="Maximum number of GPU tasks allowed to run concurrently",
    )

    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    whisper: WhisperSettings = Field(default_factory=WhisperSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    callback: CallbackSettings = Field(default_factory=CallbackSettings)
    ssrf: SsrfSettings = Field(default_factory=SsrfSettings)

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def normalize_environment(cls, v: str) -> str:
        """Normalize environment to lowercase."""
        return str(v).lower() if v else "production"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance (singleton pattern).

    Returns:
        Settings: The application settings instance.
    """
    return Settings()


# Legacy Config class for backward compatibility during migration
# This will be removed once all references are updated
class Config:
    """DEPRECATED: Legacy configuration class. Use get_settings() instead."""

    _settings = get_settings()

    # Delegate to new settings
    LANG = _settings.whisper.DEFAULT_LANG
    HF_TOKEN = _settings.whisper.HF_TOKEN
    WHISPER_MODEL = _settings.whisper.WHISPER_MODEL
    DEVICE = _settings.whisper.DEVICE
    COMPUTE_TYPE = _settings.whisper.COMPUTE_TYPE
    ENVIRONMENT = _settings.ENVIRONMENT
    LOG_LEVEL = _settings.logging.LOG_LEVEL
    AUDIO_EXTENSIONS = _settings.whisper.AUDIO_EXTENSIONS
    VIDEO_EXTENSIONS = _settings.whisper.VIDEO_EXTENSIONS
    ALLOWED_EXTENSIONS = _settings.whisper.ALLOWED_EXTENSIONS
    DB_URL = _settings.database.DB_URL
