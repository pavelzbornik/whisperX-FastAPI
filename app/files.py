"""This module provides utility functions for file handling."""

import logging
import os
from tempfile import NamedTemporaryFile
from typing import BinaryIO, Union

from fastapi import HTTPException, UploadFile

from .config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


AUDIO_EXTENSIONS = Config.AUDIO_EXTENSIONS
VIDEO_EXTENSIONS = Config.VIDEO_EXTENSIONS
ALLOWED_EXTENSIONS = Config.ALLOWED_EXTENSIONS


def validate_extension(filename, allowed_extensions: dict):
    """
    Check the file extension of the given file and compare it if its is in the allowed AUDIO and VIDEO.

    Args:
        filename (str): The name of the file.
        allowed_extensions (dict): Set of allowed file extensions.
        
    Raises:
        HTTPException: If file extension is not allowed.
    """
    if not filename:
        raise HTTPException(
            status_code=400,
            detail="Filename cannot be empty"
        )
        
    file_extension = os.path.splitext(filename)[1].lower()
    if file_extension not in allowed_extensions:
        logger.warning("Invalid file extension for file: %s", filename)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension for file {filename}. Allowed extensions: {', '.join(sorted(allowed_extensions))}",
        )


def validate_file_size(file_size: int, max_size: int = Config.MAX_FILE_SIZE_BYTES):
    """
    Validate file size against configured limits.
    
    Args:
        file_size (int): Size of the file in bytes.
        max_size (int): Maximum allowed file size in bytes.
        
    Raises:
        HTTPException: If file size exceeds limit.
    """
    if file_size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        current_size_mb = file_size / (1024 * 1024)
        logger.warning("File size %.2f MB exceeds limit of %.2f MB", current_size_mb, max_size_mb)
        raise HTTPException(
            status_code=413,
            detail=f"File size {current_size_mb:.2f} MB exceeds maximum allowed size of {max_size_mb:.0f} MB"
        )


def validate_file_content(file_content: bytes, filename: str):
    """
    Validate file content to ensure it's a valid audio/video file.
    
    Args:
        file_content (bytes): Content of the file.
        filename (str): Name of the file.
        
    Raises:
        HTTPException: If file content is invalid.
    """
    if not file_content:
        raise HTTPException(
            status_code=400,
            detail="File content cannot be empty"
        )
    
    # Basic magic number validation for common audio/video formats
    magic_numbers = {
        b'ID3': ['.mp3'],
        b'RIFF': ['.wav', '.avi'],
        b'\x00\x00\x00\x18ftypmp4': ['.mp4'],
        b'\x00\x00\x00\x1cftypmp4': ['.mp4'],
        b'OggS': ['.ogg', '.oga'],
        b'fLaC': ['.flac'],
        b'#!AMR': ['.amr'],
    }
    
    file_extension = os.path.splitext(filename)[1].lower()
    file_header = file_content[:20]  # Check first 20 bytes
    
    # Check if file starts with known magic numbers
    valid_format = False
    for magic, extensions in magic_numbers.items():
        if file_header.startswith(magic) and file_extension in extensions:
            valid_format = True
            break
    
    # If no magic number match, allow the file but log a warning
    # This prevents false negatives with valid files that have unusual headers
    if not valid_format:
        logger.warning("Could not verify file format for %s, proceeding with caution", filename)


def check_file_extension(file):
    """
    Check the file extension of the given file and compare it if its is in the allowed AUDIO and VIDEO.

    Args:
        file (str): The path to the file.

    """
    validate_extension(file, ALLOWED_EXTENSIONS)


def validate_upload_file(upload_file: UploadFile) -> None:
    """
    Comprehensive validation for uploaded files.
    
    Args:
        upload_file (UploadFile): The uploaded file to validate.
        
    Raises:
        HTTPException: If validation fails.
    """
    # Validate filename
    if not upload_file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required"
        )
    
    # Validate file extension
    validate_extension(upload_file.filename, ALLOWED_EXTENSIONS)
    
    # Get file size
    if hasattr(upload_file.file, 'seek') and hasattr(upload_file.file, 'tell'):
        # For SpooledTemporaryFile and similar
        upload_file.file.seek(0, 2)  # Seek to end
        file_size = upload_file.file.tell()
        upload_file.file.seek(0)  # Reset to beginning
    else:
        # Fallback: read content to get size (less efficient)
        content = upload_file.file.read()
        file_size = len(content)
        upload_file.file.seek(0)  # Reset file pointer
    
    # Validate file size
    validate_file_size(file_size)
    
    logger.info("File validation passed for %s (%.2f MB)", 
                upload_file.filename, file_size / (1024 * 1024))


def save_temporary_file(temporary_file: Union[BinaryIO, UploadFile], original_filename: str) -> str:
    """
    Save the contents of a file to a named temporary file with enhanced error handling.

    Args:
        temporary_file: The file object to save.
        original_filename (str): Original filename to preserve extension.
        
    Returns:
        str: Path to the saved temporary file.
        
    Raises:
        HTTPException: If file saving fails.
    """
    try:
        # Extract the original file extension
        _, original_extension = os.path.splitext(original_filename)

        # Create a temporary file with the original extension
        temp_filename = NamedTemporaryFile(suffix=original_extension, delete=False).name

        # Handle different file types
        if isinstance(temporary_file, UploadFile):
            file_content = temporary_file.file.read()
        else:
            file_content = temporary_file.read()
        
        # Validate file content
        validate_file_content(file_content, original_filename)

        # Write the contents to the temporary file
        with open(temp_filename, "wb") as dest:
            dest.write(file_content)

        logger.info("Successfully saved temporary file: %s -> %s", 
                   original_filename, temp_filename)
        return temp_filename
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error("Failed to save temporary file %s: %s", original_filename, str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save uploaded file: {str(e)}"
        )
