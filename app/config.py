"""Configuration module for the WhisperX FastAPI application."""

import os
import warnings
from typing import Optional

import torch
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


def get_env_var(key: str, default: Optional[str] = None, required: bool = False, sensitive: bool = False) -> Optional[str]:
    """
    Safely get environment variable with validation.
    
    Args:
        key: Environment variable name
        default: Default value if not found
        required: Whether the variable is required
        sensitive: Whether to mask the value in logs
        
    Returns:
        Environment variable value or default
        
    Raises:
        ValueError: If required variable is missing
    """
    value = os.getenv(key, default)
    
    if required and not value:
        raise ValueError(f"Required environment variable '{key}' is not set")
    
    if value and sensitive and len(value) < 8:
        warnings.warn(f"Environment variable '{key}' appears to be too short for a sensitive value", UserWarning)
    
    return value


class Config:
    """Configuration class for WhisperX FastAPI application settings."""

    LANG = get_env_var("DEFAULT_LANG", "en")
    
    # Sensitive configuration - avoid logging these values
    HF_TOKEN = get_env_var("HF_TOKEN", sensitive=True)
    
    WHISPER_MODEL = get_env_var("WHISPER_MODEL", "tiny")  # Set default model
    DEVICE = get_env_var("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    COMPUTE_TYPE = get_env_var(
        "COMPUTE_TYPE", "float16" if torch.cuda.is_available() else "int8"
    )
    ENVIRONMENT = get_env_var("ENVIRONMENT", "production").lower()
    LOG_LEVEL = get_env_var(
        "LOG_LEVEL", "DEBUG" if ENVIRONMENT == "development" else "INFO"
    ).upper()
    
    # Validate environment values
    if ENVIRONMENT not in ["development", "staging", "production"]:
        ENVIRONMENT = "production"
        
    if LOG_LEVEL not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        LOG_LEVEL = "INFO"

    AUDIO_EXTENSIONS = {
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
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".wmv", ".mkv"}
    ALLOWED_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

    DB_URL = get_env_var("DB_URL", "sqlite:///records.db")
    
    # File upload validation settings
    MAX_FILE_SIZE_MB = int(get_env_var("MAX_FILE_SIZE_MB", "500"))  # 500MB default
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    
    # Request timeout settings
    REQUEST_TIMEOUT_SECONDS = int(get_env_var("REQUEST_TIMEOUT_SECONDS", "3600"))  # 1 hour default
    
    # Security settings
    ENABLE_CORS = get_env_var("ENABLE_CORS", "false").lower() == "true"
