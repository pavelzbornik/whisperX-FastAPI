import logging
import os
from tempfile import NamedTemporaryFile

from fastapi import HTTPException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


def validate_extension(filename, allowed_extensions: dict):
    """
    Check the file extension of the given file and compare it if its is in the allowed AUDIO and VIDEO.

    Args:
        file (str): The path to the file.

    """
    file_extension = os.path.splitext(filename)[1].lower()
    if file_extension not in allowed_extensions:
        logger.info("Received file upload request: %s", filename)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension for file {filename} . Allowed: {allowed_extensions}",
        )


def check_file_extension(file):
    """
    Check the file extension of the given file and compare it if its is in the allowed AUDIO and VIDEO.

    Args:
        file (str): The path to the file.

    """
    validate_extension(file, ALLOWED_EXTENSIONS)


def save_temporary_file(temporary_file, original_filename):
    """
    Save the contents of a SpooledTemporaryFile to a named temporary file
    and return the file path while preserving the original file extension.
    """
    # Extract the original file extension
    _, original_extension = os.path.splitext(original_filename)

    # Create a temporary file with the original extension
    temp_filename = NamedTemporaryFile(suffix=original_extension, delete=False).name

    # Write the contents of the SpooledTemporaryFile to the temporary file
    with open(temp_filename, "wb") as dest:
        dest.write(temporary_file.read())

    return temp_filename
