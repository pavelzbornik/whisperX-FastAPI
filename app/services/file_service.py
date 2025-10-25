"""Service for file operations including uploads, downloads, and validation."""

import os
import re
from tempfile import NamedTemporaryFile
from typing import Optional

import requests
from fastapi import HTTPException, UploadFile

from app.core.config import Config
from app.core.logging import logger
from app.core.logging.audit_logger import AuditLogger


class FileService:
    """Service for handling file operations.

    This service provides utilities for file uploads, URL downloads,
    filename sanitization, and file extension validation.
    """

    @staticmethod
    def secure_filename(filename: str) -> str:
        """
        Sanitize the filename to ensure it is safe for use in file systems.

        Args:
            filename: The original filename to sanitize

        Returns:
            Sanitized filename safe for filesystem use

        Raises:
            ValueError: If filename is empty or invalid after sanitization
        """
        filename = os.path.basename(filename)
        # Only allow alphanumerics, dash, underscore, and dot
        filename = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)
        # Replace multiple consecutive dots or underscores with a single underscore
        filename = re.sub(r"[._]{2,}", "_", filename)
        # Remove leading dots or underscores
        filename = re.sub(r"^[._]+", "", filename)
        # Ensure filename is not empty or problematic
        if not filename or filename in {".", ".."}:
            raise ValueError(
                "Filename is empty or contains only special characters after sanitization."
            )
        return filename

    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: set[str]) -> str:
        """
        Validate that the file extension is in the allowed set.

        Args:
            filename: Name of the file to validate
            allowed_extensions: Set of allowed file extensions (e.g., {'.mp3', '.wav'})

        Returns:
            The validated file extension in lowercase

        Raises:
            HTTPException: If the file extension is not in the allowed set
        """
        file_extension = os.path.splitext(filename)[1].lower()
        if file_extension not in allowed_extensions:
            logger.warning(
                "Invalid file extension for file %s. Extension: %s, Allowed: %s",
                filename,
                file_extension,
                allowed_extensions,
            )
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file extension for file {filename}. Allowed: {allowed_extensions}",
            )
        return file_extension

    @staticmethod
    def save_upload(
        file: UploadFile,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> str:
        """
        Save an uploaded file to a temporary location.

        Args:
            file: The uploaded file to save
            user_id: User identifier (optional)
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)

        Returns:
            Path to the temporary file

        Raises:
            HTTPException: If filename is missing or invalid
        """
        if file.filename is None:
            raise HTTPException(status_code=400, detail="Filename is missing")

        # Extract the original file extension
        _, original_extension = os.path.splitext(file.filename)

        # Create a temporary file with the original extension
        temp_file = NamedTemporaryFile(suffix=original_extension, delete=False)
        content = file.file.read()
        temp_file.write(content)
        temp_file.close()

        logger.debug(
            "Saved uploaded file %s to temporary location: %s",
            file.filename,
            temp_file.name,
        )

        # Audit log the file upload
        AuditLogger.log_file_uploaded(
            file_name=file.filename,
            file_size=len(content),
            content_type=file.content_type,
            user_id=user_id,
            ip_address=ip_address,
            request_id=request_id,
        )

        return temp_file.name

    @staticmethod
    def download_from_url(
        url: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Download a file from a URL to a temporary location.

        Args:
            url: URL of the file to download
            user_id: User identifier (optional)
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)

        Returns:
            Tuple of (temp_file_path, original_filename)

        Raises:
            ValueError: If the URL is invalid or file extension is not allowed
            HTTPException: If download fails
        """
        logger.info("Downloading file from URL: %s", url)

        try:
            with requests.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()

                # Check for filename in Content-Disposition header
                content_disposition = response.headers.get("Content-Disposition")
                if content_disposition and "filename=" in content_disposition:
                    filename = content_disposition.split("filename=")[1].strip('"')
                else:
                    # Fall back to extracting from the URL path
                    filename = os.path.basename(url)
                    filename = FileService.secure_filename(filename)

                # Get the file extension
                _, ext_candidate = os.path.splitext(filename)
                ext_candidate = ext_candidate.lower().strip()

                # Validate extension format
                if not ext_candidate or not ext_candidate.startswith("."):
                    raise ValueError(f"Invalid file extension: {ext_candidate}")

                ext_clean = ext_candidate[1:]  # remove leading dot for lookup

                # Map to canonical extension from allowed set
                extension_to_suffix = {
                    ext.lower().lstrip("."): ext for ext in Config.ALLOWED_EXTENSIONS
                }
                if ext_clean not in extension_to_suffix:
                    raise ValueError(f"Invalid file extension: {ext_candidate}")

                # Use the canonical extension from allowed set
                safe_suffix = extension_to_suffix[ext_clean]

                # Save the file to a temporary location
                temp_audio_file = NamedTemporaryFile(suffix=safe_suffix, delete=False)
                file_size = 0
                for chunk in response.iter_content(chunk_size=8192):
                    temp_audio_file.write(chunk)
                    file_size += len(chunk)
                temp_audio_file.close()

                logger.info(
                    "File downloaded successfully: %s -> %s",
                    url,
                    temp_audio_file.name,
                )

                # Audit log the file download
                AuditLogger.log_file_uploaded(
                    file_name=filename,
                    file_size=file_size,
                    content_type=response.headers.get("Content-Type"),
                    user_id=user_id,
                    ip_address=ip_address,
                    request_id=request_id,
                )

                return temp_audio_file.name, filename

        except requests.RequestException as e:
            logger.error("Failed to download file from URL %s: %s", url, str(e))
            raise HTTPException(
                status_code=400,
                detail=f"Failed to download file from URL: {str(e)}",
            )
