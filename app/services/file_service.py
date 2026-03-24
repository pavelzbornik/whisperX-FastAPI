"""Service for file operations including uploads, downloads, and validation."""

import os
import re
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

import requests
from fastapi import HTTPException, UploadFile

from app.core.config import get_settings
from app.core.exceptions import FileDownloadError, UnsupportedFileExtensionError
from app.core.logging import logger
from app.core.url_validator import validate_url


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
    def save_upload(file: UploadFile) -> str:
        """
        Save an uploaded file to a temporary location.

        Args:
            file: The uploaded file to save

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
        temp_file.write(file.file.read())
        temp_file.close()

        logger.debug(
            "Saved uploaded file %s to temporary location: %s",
            file.filename,
            temp_file.name,
        )

        return temp_file.name

    @staticmethod
    def _validate_url_extension(url: str) -> tuple[str, str]:
        """Validate URL file extension before making an HTTP request.

        Args:
            url: The URL to validate

        Returns:
            Tuple of (filename, canonical_extension)

        Raises:
            UnsupportedFileExtensionError: If the file extension is not allowed
        """
        # Extract filename from URL path
        url_path = urlparse(url).path
        filename = os.path.basename(url_path)
        if filename:
            filename = FileService.secure_filename(filename)

        _, ext_candidate = os.path.splitext(filename)
        ext_candidate = ext_candidate.lower().strip()

        allowed = get_settings().whisper.ALLOWED_EXTENSIONS
        extension_to_suffix = {ext.lower().lstrip("."): ext for ext in allowed}

        if not ext_candidate or not ext_candidate.startswith("."):
            raise UnsupportedFileExtensionError(
                filename=filename or url,
                extension=ext_candidate or "(none)",
                allowed=allowed,
            )

        ext_clean = ext_candidate[1:]
        if ext_clean not in extension_to_suffix:
            raise UnsupportedFileExtensionError(
                filename=filename,
                extension=ext_candidate,
                allowed=allowed,
            )

        return filename, extension_to_suffix[ext_clean]

    @staticmethod
    def download_from_url(url: str) -> tuple[str, str]:
        """Download a file from a URL to a temporary location.

        Validates the URL against SSRF rules and checks the file extension
        BEFORE making any HTTP request.

        Args:
            url: URL of the file to download

        Returns:
            Tuple of (temp_file_path, original_filename)

        Raises:
            SsrfBlockedError: If the URL is blocked by SSRF protection
            UnsupportedFileExtensionError: If the file extension is not allowed
            FileDownloadError: If the download fails
        """
        logger.info("Downloading file from URL: %s", url)

        # Validate URL against SSRF rules BEFORE making any request
        validate_url(url)

        # Validate extension from URL BEFORE making any request
        filename, safe_suffix = FileService._validate_url_extension(url)

        try:
            session = requests.Session()
            session.max_redirects = 10

            # Validate each redirect target against SSRF rules
            def _check_redirect(
                response: requests.Response, *args: object, **kwargs: object
            ) -> None:  # noqa: ARG001
                if response.is_redirect:
                    location = response.headers.get("Location", "")
                    if location:
                        validate_url(location)

            session.hooks["response"].append(_check_redirect)

            with session.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()

                # Check for filename in Content-Disposition header
                content_disposition = response.headers.get("Content-Disposition")
                if content_disposition and "filename=" in content_disposition:
                    cd_filename = content_disposition.split("filename=")[1].strip('"')
                    cd_filename = FileService.secure_filename(cd_filename)
                    # Validate Content-Disposition extension too (defense in depth)
                    _, cd_ext = os.path.splitext(cd_filename)
                    allowed = get_settings().whisper.ALLOWED_EXTENSIONS
                    extension_to_suffix = {
                        ext.lower().lstrip("."): ext for ext in allowed
                    }
                    cd_ext_clean = cd_ext.lower().strip().lstrip(".")
                    if cd_ext_clean in extension_to_suffix:
                        filename = cd_filename
                        safe_suffix = extension_to_suffix[cd_ext_clean]

                # Save the file to a temporary location
                temp_audio_file = NamedTemporaryFile(suffix=safe_suffix, delete=False)
                for chunk in response.iter_content(chunk_size=8192):
                    temp_audio_file.write(chunk)
                temp_audio_file.close()

                logger.info(
                    "File downloaded successfully: %s -> %s",
                    url,
                    temp_audio_file.name,
                )

                return temp_audio_file.name, filename

        except requests.RequestException as e:
            logger.error("Failed to download file from URL %s: %s", url, str(e))
            raise FileDownloadError(url=url, original_error=e)
