"""Configuration module for the WhisperX FastAPI application."""

import os

import torch
from dotenv import load_dotenv

from .schemas import ComputeType, Device, WhisperModel

# Load environment variables from .env
load_dotenv()


class Config:
    """Configuration class for WhisperX FastAPI application settings."""

    LANG = os.getenv("DEFAULT_LANG", "en")
    HF_TOKEN = os.getenv("HF_TOKEN")

    # Parse WHISPER_MODEL from env or use default
    _whisper_model_str = os.getenv("WHISPER_MODEL", "tiny")
    try:
        WHISPER_MODEL = WhisperModel(_whisper_model_str)
    except ValueError:
        # If invalid value, default to tiny
        WHISPER_MODEL = WhisperModel.tiny

    # Parse DEVICE from env or use default based on CUDA availability
    _device_str = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    try:
        DEVICE = Device(_device_str)
    except ValueError:
        # If invalid value, default based on CUDA availability
        DEVICE = Device.cuda if torch.cuda.is_available() else Device.cpu

    # Parse COMPUTE_TYPE from env or use default based on CUDA availability
    _compute_type_str = os.getenv(
        "COMPUTE_TYPE", "float16" if torch.cuda.is_available() else "int8"
    )
    try:
        COMPUTE_TYPE = ComputeType(_compute_type_str)
    except ValueError:
        # If invalid value, default based on CUDA availability
        COMPUTE_TYPE = (
            ComputeType.float16 if torch.cuda.is_available() else ComputeType.int8
        )
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()
    LOG_LEVEL = os.getenv(
        "LOG_LEVEL", "DEBUG" if ENVIRONMENT == "development" else "INFO"
    ).upper()

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

    DB_URL = os.getenv("DB_URL", "sqlite:///records.db")
