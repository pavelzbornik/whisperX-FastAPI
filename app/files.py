"""This module provides utility functions for file handling."""

from .logger import logger
import os
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import HTTPException

from .config import Config


AUDIO_EXTENSIONS = Config.AUDIO_EXTENSIONS
VIDEO_EXTENSIONS = Config.VIDEO_EXTENSIONS
ALLOWED_EXTENSIONS = Config.ALLOWED_EXTENSIONS


def validate_extension(filename: str, allowed_extensions: set[str]) -> str:
    """
    Check the file extension of the given file and compare it if its is in the allowed AUDIO and VIDEO.

    Args:
        filename (str): The path to the file.
        allowed_extensions (set[str]): Set of allowed file extensions.

    Returns:
        str: The validated file extension in lowercase.

    Raises:
        HTTPException: If the file extension is not in the allowed set.
    """
    file_extension = os.path.splitext(filename)[1].lower()
    if file_extension not in allowed_extensions:
        logger.info("Received file upload request: %s", filename)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension for file {filename} . Allowed: {allowed_extensions}",
        )
    return file_extension


def check_file_extension(file: str) -> str:
    """
    Check the file extension of the given file and compare it if its is in the allowed AUDIO and VIDEO.

    Args:
        file (str): The path to the file.

    Returns:
        str: The validated file extension in lowercase.
    """
    return validate_extension(file, ALLOWED_EXTENSIONS)


def save_temporary_file(temporary_file: Any, original_filename: str) -> str:
    """
    Save the contents of a SpooledTemporaryFile to a named temporary file.

    Return the file path while preserving the original file extension.
    """
    # Extract the original file extension
    _, original_extension = os.path.splitext(original_filename)

    # Create a temporary file with the original extension
    temp_filename = NamedTemporaryFile(suffix=original_extension, delete=False).name

    # Write the contents of the SpooledTemporaryFile to the temporary file
    with open(temp_filename, "wb") as dest:
        dest.write(temporary_file.read())

    return temp_filename
