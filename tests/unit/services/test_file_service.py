"""Unit tests for FileService."""

import os
from tempfile import NamedTemporaryFile

import pytest
from fastapi import HTTPException, UploadFile

from app.services.file_service import FileService


class TestFileService:
    """Test suite for FileService."""

    def test_secure_filename_valid(self) -> None:
        """Test secure_filename with valid filename."""
        filename = "my_test_file.mp3"
        result = FileService.secure_filename(filename)
        assert result == "my_test_file.mp3"

    def test_secure_filename_with_special_chars(self) -> None:
        """Test secure_filename removes special characters."""
        filename = "my@test#file$.mp3"
        result = FileService.secure_filename(filename)
        # The $ at the end gets replaced, then the multiple dots/underscores get collapsed
        assert result == "my_test_file_mp3"

    def test_secure_filename_with_multiple_dots(self) -> None:
        """Test secure_filename handles multiple dots."""
        filename = "my..test...file.mp3"
        result = FileService.secure_filename(filename)
        assert result == "my_test_file.mp3"

    def test_secure_filename_with_leading_dots(self) -> None:
        """Test secure_filename removes leading dots."""
        filename = "...my_test_file.mp3"
        result = FileService.secure_filename(filename)
        assert result == "my_test_file.mp3"

    def test_secure_filename_empty_raises_error(self) -> None:
        """Test secure_filename raises error for empty filename."""
        with pytest.raises(ValueError, match="Filename is empty"):
            FileService.secure_filename("")

    def test_secure_filename_only_special_chars_raises_error(self) -> None:
        """Test secure_filename raises error for filename with only special chars."""
        with pytest.raises(ValueError, match="Filename is empty"):
            FileService.secure_filename("@#$%^&*()")

    def test_validate_file_extension_valid(self) -> None:
        """Test validate_file_extension with valid extension."""
        allowed = {".mp3", ".wav", ".flac"}
        result = FileService.validate_file_extension("test.mp3", allowed)
        assert result == ".mp3"

    def test_validate_file_extension_case_insensitive(self) -> None:
        """Test validate_file_extension is case insensitive."""
        allowed = {".mp3", ".wav", ".flac"}
        result = FileService.validate_file_extension("test.MP3", allowed)
        assert result == ".mp3"

    def test_validate_file_extension_invalid_raises_error(self) -> None:
        """Test validate_file_extension raises error for invalid extension."""
        allowed = {".mp3", ".wav", ".flac"}
        with pytest.raises(HTTPException) as exc_info:
            FileService.validate_file_extension("test.txt", allowed)
        assert exc_info.value.status_code == 400
        assert "Invalid file extension" in exc_info.value.detail

    def test_save_upload_success(self) -> None:
        """Test save_upload successfully saves a file."""
        # Create a mock upload file
        content = b"test audio content"
        temp_file = NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_file.write(content)
        temp_file.seek(0)

        # Create UploadFile mock
        upload_file = UploadFile(
            filename="test.mp3",
            file=temp_file,  # type: ignore[arg-type]
        )

        try:
            # Save the upload
            result_path = FileService.save_upload(upload_file)

            # Verify file was created
            assert os.path.exists(result_path)
            assert result_path.endswith(".mp3")

            # Verify content
            with open(result_path, "rb") as f:
                saved_content = f.read()
            assert saved_content == content

            # Cleanup
            os.unlink(result_path)
        finally:
            temp_file.close()
            os.unlink(temp_file.name)

    def test_save_upload_missing_filename_raises_error(self) -> None:
        """Test save_upload raises error when filename is missing."""
        # Create UploadFile with no filename
        temp_file = NamedTemporaryFile(delete=False)
        upload_file = UploadFile(filename=None, file=temp_file)  # type: ignore[arg-type]

        try:
            with pytest.raises(HTTPException) as exc_info:
                FileService.save_upload(upload_file)
            assert exc_info.value.status_code == 400
            assert "Filename is missing" in exc_info.value.detail
        finally:
            temp_file.close()
            os.unlink(temp_file.name)

    def test_download_from_url_invalid_extension_raises_error(self) -> None:
        """Test download_from_url raises error for invalid extension."""
        # Mock the requests.get to avoid network calls
        import unittest.mock as mock

        # Create a mock response with invalid extension
        mock_response = mock.MagicMock()
        mock_response.headers.get.return_value = None

        with mock.patch("app.services.file_service.requests.get") as mock_get:
            mock_get.return_value.__enter__.return_value = mock_response

            # Use a URL with invalid extension
            url = "https://example.com/test.txt"
            with pytest.raises(ValueError, match="Invalid file extension"):
                FileService.download_from_url(url)
