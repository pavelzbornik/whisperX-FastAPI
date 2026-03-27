"""Service for file operations including uploads, downloads, and validation."""

import os
import re
import socket
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin, urlparse

import requests
import urllib3.util.connection
from fastapi import HTTPException, UploadFile
from requests.adapters import HTTPAdapter

from app.core.config import get_settings
from app.core.exceptions import FileDownloadError, UnsupportedFileExtensionError
from app.core.logging import logger
from app.core.url_validator import validate_url


class _PinnedIPAdapter(HTTPAdapter):
    """HTTP adapter that pins DNS resolution to a validated IP.

    Prevents DNS rebinding (TOCTOU) attacks by temporarily overriding
    urllib3's create_connection to resolve to the pinned IP. The URL
    hostname is preserved for correct TLS SNI and certificate verification.
    """

    def __init__(self, pinned_ip: str) -> None:
        """Initialize with the IP to pin connections to."""
        self.pinned_ip = pinned_ip
        super().__init__()

    def send(
        self,
        request: requests.PreparedRequest,
        stream: bool = False,
        timeout: float | tuple[float, float] | tuple[float, None] | None = None,
        verify: bool | str = True,
        cert: bytes | str | tuple[bytes | str, bytes | str] | None = None,
        proxies: object = None,
    ) -> requests.Response:
        """Send request with pinned DNS resolution."""
        original_create = urllib3.util.connection.create_connection
        pinned_ip = self.pinned_ip

        def _pinned(address: tuple[str, int], **kw: object) -> socket.socket:
            _host, port = address
            return original_create((pinned_ip, port), **kw)  # type: ignore[arg-type]

        urllib3.util.connection.create_connection = _pinned  # type: ignore[assignment]
        try:
            return super().send(
                request,
                stream=stream,
                timeout=timeout,
                verify=verify,
                cert=cert,
                proxies=proxies,  # type: ignore[arg-type]
            )
        finally:
            urllib3.util.connection.create_connection = original_create


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
    def _try_parse_url_extension(url: str) -> tuple[str, str | None]:
        """Try to extract a valid file extension from a URL path.

        Args:
            url: The URL to extract the extension from

        Returns:
            Tuple of (filename, canonical_extension_or_None).
            Extension is None if the URL has no recognizable extension,
            allowing Content-Disposition fallback after download.
        """
        url_path = urlparse(url).path
        filename = os.path.basename(url_path)
        if filename:
            try:
                filename = FileService.secure_filename(filename)
            except ValueError:
                return "", None

        _, ext_candidate = os.path.splitext(filename)
        ext_candidate = ext_candidate.lower().strip()

        if not ext_candidate or not ext_candidate.startswith("."):
            return filename, None

        allowed = get_settings().whisper.ALLOWED_EXTENSIONS
        extension_to_suffix = {ext.lower().lstrip("."): ext for ext in allowed}
        ext_clean = ext_candidate[1:]

        if ext_clean not in extension_to_suffix:
            return filename, None

        return filename, extension_to_suffix[ext_clean]

    @staticmethod
    def _resolve_extension(
        filename: str,
        response: requests.Response,
        url_extension: str | None,
    ) -> tuple[str, str]:
        """Resolve the final filename and extension from URL and response headers.

        Args:
            filename: Filename extracted from URL path
            response: HTTP response to check Content-Disposition
            url_extension: Extension from URL, or None

        Returns:
            Tuple of (final_filename, canonical_extension)

        Raises:
            UnsupportedFileExtensionError: If no valid extension found
        """
        allowed = get_settings().whisper.ALLOWED_EXTENSIONS
        extension_to_suffix = {ext.lower().lstrip("."): ext for ext in allowed}

        # Try Content-Disposition header first
        content_disposition = response.headers.get("Content-Disposition")
        if content_disposition and "filename=" in content_disposition:
            cd_filename = content_disposition.split("filename=")[1].strip('"')
            try:
                cd_filename = FileService.secure_filename(cd_filename)
            except ValueError:
                pass
            else:
                _, cd_ext = os.path.splitext(cd_filename)
                cd_ext_clean = cd_ext.lower().strip().lstrip(".")
                if cd_ext_clean in extension_to_suffix:
                    return cd_filename, extension_to_suffix[cd_ext_clean]

        # Fall back to URL extension
        if url_extension:
            return filename, url_extension

        # No valid extension found from either source
        raise UnsupportedFileExtensionError(
            filename=filename or "(unknown)",
            extension="(none)",
            allowed=allowed,
        )

    @staticmethod
    def download_from_url(url: str) -> tuple[str, str]:
        """Download a file from a URL to a temporary location.

        Validates the URL against SSRF rules before making any HTTP request.
        File extension is resolved from the URL path or Content-Disposition header.

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
        # Returns a pinned IP to prevent DNS rebinding (TOCTOU) attacks
        _, pinned_ip = validate_url(url)

        # Try to extract extension from URL (may be None for CDN/API URLs)
        filename, url_extension = FileService._try_parse_url_extension(url)

        try:
            with requests.Session() as session:
                session.max_redirects = 10

                # Pin connections to the validated IP to prevent DNS rebinding
                if pinned_ip:
                    adapter = _PinnedIPAdapter(pinned_ip)
                    session.mount("http://", adapter)
                    session.mount("https://", adapter)

                # Validate each redirect target against SSRF rules
                def _check_redirect(
                    response: requests.Response, *args: object, **kwargs: object
                ) -> None:  # noqa: ARG001
                    if response.is_redirect:
                        location = response.headers.get("Location", "")
                        if location:
                            absolute_url = urljoin(str(response.url), location)
                            # Validate and get new pinned IP for redirect target
                            _, redirect_ip = validate_url(absolute_url)
                            if redirect_ip:
                                adapter = _PinnedIPAdapter(redirect_ip)
                                session.mount("http://", adapter)
                                session.mount("https://", adapter)

                session.hooks["response"].append(_check_redirect)

                # codeql[py/full-ssrf] URL validated by validate_url() above
                with session.get(url, stream=True, timeout=30) as response:
                    response.raise_for_status()

                    # Resolve final filename and extension
                    final_filename, safe_suffix = FileService._resolve_extension(
                        filename, response, url_extension
                    )

                    # Save the file to a temporary location
                    temp_audio_file = NamedTemporaryFile(
                        suffix=safe_suffix, delete=False
                    )
                    for chunk in response.iter_content(chunk_size=8192):
                        temp_audio_file.write(chunk)
                    temp_audio_file.close()

                    logger.info(
                        "File downloaded successfully: %s -> %s",
                        url,
                        temp_audio_file.name,
                    )

                    return temp_audio_file.name, final_filename

        except requests.RequestException as e:
            logger.error("Failed to download file from URL %s: %s", url, str(e))
            raise FileDownloadError(url=url, original_error=e) from e
