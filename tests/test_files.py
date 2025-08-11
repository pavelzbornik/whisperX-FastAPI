"""Tests for the files module."""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.files import (
    ALLOWED_EXTENSIONS,
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    check_file_extension,
    save_temporary_file,
    validate_extension,
)


class TestValidateExtension:
    """Test cases for validate_extension function."""

    def test_validate_extension_valid_audio(self):
        """Test validation with valid audio extension."""
        valid_extensions = {".mp3", ".wav", ".aac"}
        
        # Should not raise exception
        validate_extension("test.mp3", valid_extensions)
        validate_extension("audio.WAV", valid_extensions)  # Case insensitive
        validate_extension("music.Aac", valid_extensions)

    def test_validate_extension_valid_video(self):
        """Test validation with valid video extension."""
        valid_extensions = {".mp4", ".avi", ".mov"}
        
        # Should not raise exception
        validate_extension("video.mp4", valid_extensions)
        validate_extension("movie.AVI", valid_extensions)  # Case insensitive
        validate_extension("clip.Mov", valid_extensions)

    def test_validate_extension_invalid_extension(self):
        """Test validation with invalid extension."""
        valid_extensions = {".mp3", ".wav"}
        
        with pytest.raises(HTTPException) as exc_info:
            validate_extension("document.txt", valid_extensions)
        
        assert exc_info.value.status_code == 400
        assert "Invalid file extension for file document.txt" in str(exc_info.value.detail)
        assert "Allowed: {'.mp3', '.wav'}" in str(exc_info.value.detail) or "Allowed: {'.wav', '.mp3'}" in str(exc_info.value.detail)

    def test_validate_extension_no_extension(self):
        """Test validation with filename without extension."""
        valid_extensions = {".mp3", ".wav"}
        
        with pytest.raises(HTTPException) as exc_info:
            validate_extension("filename_without_extension", valid_extensions)
        
        assert exc_info.value.status_code == 400
        assert "Invalid file extension for file filename_without_extension" in str(exc_info.value.detail)

    def test_validate_extension_empty_string(self):
        """Test validation with empty filename."""
        valid_extensions = {".mp3", ".wav"}
        
        with pytest.raises(HTTPException) as exc_info:
            validate_extension("", valid_extensions)
        
        assert exc_info.value.status_code == 400

    def test_validate_extension_case_insensitive(self):
        """Test that extension validation is case insensitive."""
        valid_extensions = {".mp3", ".wav", ".mp4"}  # Use lowercase for consistency
        
        # These should all pass
        validate_extension("test.MP3", valid_extensions)
        validate_extension("test.WAV", valid_extensions)
        validate_extension("test.MP4", valid_extensions)
        validate_extension("test.Mp4", valid_extensions)

    def test_validate_extension_with_multiple_dots(self):
        """Test validation with filename containing multiple dots."""
        valid_extensions = {".mp3", ".wav"}
        
        # Should work correctly with multiple dots in filename
        validate_extension("my.file.name.mp3", valid_extensions)
        
        # Should fail if the final extension is invalid
        with pytest.raises(HTTPException):
            validate_extension("my.file.name.txt", valid_extensions)

    @patch("app.files.logger.info")
    def test_validate_extension_logs_invalid_attempts(self, mock_logger):
        """Test that invalid extension attempts are logged."""
        valid_extensions = {".mp3"}
        
        with pytest.raises(HTTPException):
            validate_extension("invalid.txt", valid_extensions)
        
        mock_logger.assert_called_once_with("Received file upload request: %s", "invalid.txt")


class TestCheckFileExtension:
    """Test cases for check_file_extension function."""

    @patch("app.files.validate_extension")
    def test_check_file_extension_calls_validate(self, mock_validate):
        """Test that check_file_extension calls validate_extension with ALLOWED_EXTENSIONS."""
        test_file = "test.mp3"
        
        check_file_extension(test_file)
        
        mock_validate.assert_called_once_with(test_file, ALLOWED_EXTENSIONS)

    def test_check_file_extension_with_valid_audio(self):
        """Test check_file_extension with valid audio file."""
        # Assuming AUDIO_EXTENSIONS includes .mp3
        if ".mp3" in ALLOWED_EXTENSIONS:
            # Should not raise exception
            check_file_extension("audio.mp3")

    def test_check_file_extension_with_valid_video(self):
        """Test check_file_extension with valid video file."""
        # Assuming VIDEO_EXTENSIONS includes .mp4
        if ".mp4" in ALLOWED_EXTENSIONS:
            # Should not raise exception
            check_file_extension("video.mp4")

    def test_check_file_extension_with_invalid_file(self):
        """Test check_file_extension with invalid file extension."""
        with pytest.raises(HTTPException) as exc_info:
            check_file_extension("document.pdf")
        
        assert exc_info.value.status_code == 400


class TestSaveTemporaryFile:
    """Test cases for save_temporary_file function."""

    def test_save_temporary_file_with_mp3_extension(self):
        """Test saving temporary file with .mp3 extension."""
        # Create mock temporary file content
        test_content = b"fake audio data"
        mock_temp_file = Mock()
        mock_temp_file.read.return_value = test_content
        
        original_filename = "audio.mp3"
        
        with patch("app.files.NamedTemporaryFile") as mock_named_temp:
            mock_named_temp.return_value.name = "/tmp/test_audio.mp3"
            
            with patch("builtins.open", create=True) as mock_open:
                mock_file = Mock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = save_temporary_file(mock_temp_file, original_filename)
                
                # Verify NamedTemporaryFile was called with correct suffix
                mock_named_temp.assert_called_once_with(suffix=".mp3", delete=False)
                
                # Verify file was opened for writing
                mock_open.assert_called_once_with("/tmp/test_audio.mp3", "wb")
                
                # Verify content was written
                mock_file.write.assert_called_once_with(test_content)
                
                # Verify return value
                assert result == "/tmp/test_audio.mp3"

    def test_save_temporary_file_with_video_extension(self):
        """Test saving temporary file with video extension."""
        test_content = b"fake video data"
        mock_temp_file = Mock()
        mock_temp_file.read.return_value = test_content
        
        original_filename = "movie.mp4"
        
        with patch("app.files.NamedTemporaryFile") as mock_named_temp:
            mock_named_temp.return_value.name = "/tmp/test_video.mp4"
            
            with patch("builtins.open", create=True) as mock_open:
                mock_file = Mock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = save_temporary_file(mock_temp_file, original_filename)
                
                mock_named_temp.assert_called_once_with(suffix=".mp4", delete=False)
                mock_file.write.assert_called_once_with(test_content)
                assert result == "/tmp/test_video.mp4"

    def test_save_temporary_file_no_extension(self):
        """Test saving temporary file without extension."""
        test_content = b"some data"
        mock_temp_file = Mock()
        mock_temp_file.read.return_value = test_content
        
        original_filename = "filename_without_extension"
        
        with patch("app.files.NamedTemporaryFile") as mock_named_temp:
            mock_named_temp.return_value.name = "/tmp/test_file"
            
            with patch("builtins.open", create=True) as mock_open:
                mock_file = Mock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = save_temporary_file(mock_temp_file, original_filename)
                
                # Should call NamedTemporaryFile with empty suffix
                mock_named_temp.assert_called_once_with(suffix="", delete=False)
                assert result == "/tmp/test_file"

    def test_save_temporary_file_multiple_extensions(self):
        """Test saving temporary file with filename containing multiple dots."""
        test_content = b"test data"
        mock_temp_file = Mock()
        mock_temp_file.read.return_value = test_content
        
        original_filename = "my.audio.file.wav"
        
        with patch("app.files.NamedTemporaryFile") as mock_named_temp:
            mock_named_temp.return_value.name = "/tmp/test.wav"
            
            with patch("builtins.open", create=True) as mock_open:
                mock_file = Mock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = save_temporary_file(mock_temp_file, original_filename)
                
                # Should extract only the final extension
                mock_named_temp.assert_called_once_with(suffix=".wav", delete=False)

    def test_save_temporary_file_case_preservation(self):
        """Test that original extension case is preserved."""
        test_content = b"test data"
        mock_temp_file = Mock()
        mock_temp_file.read.return_value = test_content
        
        original_filename = "test.MP3"  # Uppercase extension
        
        with patch("app.files.NamedTemporaryFile") as mock_named_temp:
            mock_named_temp.return_value.name = "/tmp/test.MP3"
            
            with patch("builtins.open", create=True) as mock_open:
                mock_file = Mock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = save_temporary_file(mock_temp_file, original_filename)
                
                # Should preserve the original case
                mock_named_temp.assert_called_once_with(suffix=".MP3", delete=False)

    def test_save_temporary_file_empty_content(self):
        """Test saving temporary file with empty content."""
        mock_temp_file = Mock()
        mock_temp_file.read.return_value = b""  # Empty content
        
        original_filename = "empty.mp3"
        
        with patch("app.files.NamedTemporaryFile") as mock_named_temp:
            mock_named_temp.return_value.name = "/tmp/empty.mp3"
            
            with patch("builtins.open", create=True) as mock_open:
                mock_file = Mock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = save_temporary_file(mock_temp_file, original_filename)
                
                # Should still work with empty content
                mock_file.write.assert_called_once_with(b"")
                assert result == "/tmp/empty.mp3"

    def test_save_temporary_file_integration(self):
        """Integration test with real temporary file (no mocks for file operations)."""
        # Create a real temporary file with content
        test_content = b"real test data for integration"
        
        with tempfile.NamedTemporaryFile() as mock_temp_file:
            mock_temp_file.write(test_content)
            mock_temp_file.seek(0)  # Reset to beginning for reading
            
            original_filename = "integration_test.mp3"
            
            # Only mock the NamedTemporaryFile creation, not file operations
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = os.path.join(temp_dir, "test.mp3")
                
                with patch("app.files.NamedTemporaryFile") as mock_named_temp:
                    mock_named_temp.return_value.name = temp_path
                    
                    result = save_temporary_file(mock_temp_file, original_filename)
                    
                    # Verify the file was created and contains expected content
                    assert result == temp_path
                    assert os.path.exists(temp_path)
                    
                    with open(temp_path, "rb") as f:
                        saved_content = f.read()
                        assert saved_content == test_content


class TestModuleConstants:
    """Test cases for module-level constants."""

    def test_audio_extensions_defined(self):
        """Test that AUDIO_EXTENSIONS is properly defined."""
        assert isinstance(AUDIO_EXTENSIONS, set)
        assert len(AUDIO_EXTENSIONS) > 0
        # Check for common audio extensions
        common_audio = {".mp3", ".wav", ".aac"}
        assert common_audio.issubset(AUDIO_EXTENSIONS)

    def test_video_extensions_defined(self):
        """Test that VIDEO_EXTENSIONS is properly defined."""
        assert isinstance(VIDEO_EXTENSIONS, set)
        assert len(VIDEO_EXTENSIONS) > 0
        # Check for common video extensions
        common_video = {".mp4", ".avi"}
        assert common_video.issubset(VIDEO_EXTENSIONS)

    def test_allowed_extensions_is_union(self):
        """Test that ALLOWED_EXTENSIONS is union of audio and video extensions."""
        assert isinstance(ALLOWED_EXTENSIONS, set)
        assert ALLOWED_EXTENSIONS == AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

    def test_extensions_are_lowercase(self):
        """Test that all extensions are defined in lowercase."""
        for ext in AUDIO_EXTENSIONS:
            assert ext == ext.lower(), f"Extension {ext} should be lowercase"
        
        for ext in VIDEO_EXTENSIONS:
            assert ext == ext.lower(), f"Extension {ext} should be lowercase"

    def test_extensions_start_with_dot(self):
        """Test that all extensions start with a dot."""
        for ext in ALLOWED_EXTENSIONS:
            assert ext.startswith("."), f"Extension {ext} should start with a dot"