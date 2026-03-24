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

    @pytest.mark.unit
    def test_download_from_url_ssrf_blocked_raises_error(self) -> None:
        """Test download_from_url raises SsrfBlockedError for blocked URLs."""
        import unittest.mock as mock

        from app.core.exceptions import SsrfBlockedError

        with mock.patch(
            "app.services.file_service.validate_url",
            side_effect=SsrfBlockedError(
                url="http://127.0.0.1/test.mp3", reason="blocked"
            ),
        ):
            with mock.patch(
                "app.services.file_service.requests.Session"
            ) as mock_session:
                with pytest.raises(SsrfBlockedError):
                    FileService.download_from_url("http://127.0.0.1/test.mp3")
                mock_session.return_value.get.assert_not_called()

    @pytest.mark.unit
    def test_download_from_url_no_extension_uses_content_disposition(self) -> None:
        """Test download_from_url falls back to Content-Disposition for extensionless URLs."""
        import unittest.mock as mock

        mock_response = mock.MagicMock()
        mock_response.headers = {
            "Content-Disposition": 'attachment; filename="audio.mp3"'
        }
        mock_response.raise_for_status = mock.MagicMock()
        mock_response.iter_content = mock.MagicMock(return_value=[b"fake audio"])
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        mock_session = mock.MagicMock()
        mock_session.get.return_value = mock_response

        with mock.patch("app.services.file_service.validate_url"):
            with mock.patch(
                "app.services.file_service.requests.Session",
                return_value=mock_session,
            ):
                path, filename = FileService.download_from_url(
                    "https://cdn.example.com/download/abc123"
                )
                assert filename == "audio.mp3"
                assert path.endswith(".mp3")
                os.unlink(path)
