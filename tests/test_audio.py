"""Tests for the audio module."""

import tempfile
from unittest.mock import Mock, patch

import numpy as np
import pytest

from app.audio import convert_video_to_audio, get_audio_duration, process_audio_file
from app.files import VIDEO_EXTENSIONS


class TestConvertVideoToAudio:
    """Test cases for convert_video_to_audio function."""

    @patch("app.audio.subprocess.call")
    @patch("app.audio.NamedTemporaryFile")
    def test_convert_video_to_audio(self, mock_temp_file, mock_subprocess):
        """Test converting video to audio."""
        # Mock temporary file
        mock_temp_file.return_value.name = "/tmp/test_audio.wav"
        
        # Mock subprocess call
        mock_subprocess.return_value = 0
        
        input_video = "/path/to/video.mp4"
        result = convert_video_to_audio(input_video)
        
        # Verify temporary file was created
        mock_temp_file.assert_called_once_with(delete=False)
        
        # Verify subprocess was called with correct ffmpeg command
        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0][0]
        
        expected_args = [
            "ffmpeg",
            "-y",  # Overwrite output file if it exists
            "-i",
            input_video,
            "-vn",
            "-ac",
            "1",  # Mono audio
            "-ar",
            "16000",  # Sample rate of 16kHz
            "-f",
            "wav",  # Output format WAV
            "/tmp/test_audio.wav",
        ]
        
        assert args == expected_args
        assert result == "/tmp/test_audio.wav"

    @patch("app.audio.subprocess.call")
    @patch("app.audio.NamedTemporaryFile")
    def test_convert_video_to_audio_with_different_extensions(self, mock_temp_file, mock_subprocess):
        """Test converting different video formats to audio."""
        mock_temp_file.return_value.name = "/tmp/converted.wav"
        mock_subprocess.return_value = 0
        
        video_files = [
            "/path/to/video.mp4",
            "/path/to/video.avi",
            "/path/to/video.mov",
            "/path/to/video.mkv"
        ]
        
        for video_file in video_files:
            result = convert_video_to_audio(video_file)
            assert result == "/tmp/converted.wav"

    @patch("app.audio.subprocess.call")
    @patch("app.audio.NamedTemporaryFile")
    def test_convert_video_to_audio_subprocess_failure(self, mock_temp_file, mock_subprocess):
        """Test that function continues even if subprocess fails."""
        mock_temp_file.return_value.name = "/tmp/test.wav"
        mock_subprocess.return_value = 1  # Non-zero return code indicates failure
        
        result = convert_video_to_audio("/path/to/video.mp4")
        
        # Function should still return the temp filename even if subprocess fails
        assert result == "/tmp/test.wav"


class TestProcessAudioFile:
    """Test cases for process_audio_file function."""

    @patch("app.audio.load_audio")
    @patch("app.audio.check_file_extension")
    def test_process_audio_file_with_audio_extension(self, mock_check_ext, mock_load_audio):
        """Test processing file with audio extension."""
        # Mock audio file
        audio_file = "/path/to/audio.mp3"
        mock_check_ext.return_value = ".mp3"  # Audio extension
        mock_audio_data = np.array([0.1, 0.2, 0.3])
        mock_load_audio.return_value = mock_audio_data
        
        result = process_audio_file(audio_file)
        
        mock_check_ext.assert_called_once_with(audio_file)
        mock_load_audio.assert_called_once_with(audio_file)
        np.testing.assert_array_equal(result, mock_audio_data)

    @patch("app.audio.load_audio")
    @patch("app.audio.convert_video_to_audio")
    @patch("app.audio.check_file_extension")
    def test_process_audio_file_with_video_extension(self, mock_check_ext, mock_convert, mock_load_audio):
        """Test processing file with video extension."""
        # Mock video file
        video_file = "/path/to/video.mp4"
        converted_audio = "/tmp/converted.wav"
        mock_check_ext.return_value = ".mp4"  # Video extension
        mock_convert.return_value = converted_audio
        mock_audio_data = np.array([0.1, 0.2, 0.3])
        mock_load_audio.return_value = mock_audio_data
        
        # Ensure .mp4 is in VIDEO_EXTENSIONS
        with patch("app.audio.VIDEO_EXTENSIONS", {".mp4", ".avi", ".mov"}):
            result = process_audio_file(video_file)
        
        mock_check_ext.assert_called_once_with(video_file)
        mock_convert.assert_called_once_with(video_file)
        mock_load_audio.assert_called_once_with(converted_audio)
        np.testing.assert_array_equal(result, mock_audio_data)

    @patch("app.audio.load_audio")
    @patch("app.audio.check_file_extension")
    def test_process_audio_file_with_various_audio_extensions(self, mock_check_ext, mock_load_audio):
        """Test processing files with various audio extensions."""
        audio_extensions = [".mp3", ".wav", ".aac", ".ogg", ".m4a"]
        mock_audio_data = np.array([0.1, 0.2])
        mock_load_audio.return_value = mock_audio_data
        
        for ext in audio_extensions:
            mock_check_ext.return_value = ext
            audio_file = f"/path/to/audio{ext}"
            
            result = process_audio_file(audio_file)
            
            np.testing.assert_array_equal(result, mock_audio_data)

    @patch("app.audio.load_audio")  
    @patch("app.audio.convert_video_to_audio")
    @patch("app.audio.check_file_extension")
    def test_process_audio_file_with_various_video_extensions(self, mock_check_ext, mock_convert, mock_load_audio):
        """Test processing files with various video extensions."""
        video_extensions = [".mp4", ".avi", ".mov", ".mkv"]
        mock_audio_data = np.array([0.5, 0.6])
        mock_load_audio.return_value = mock_audio_data
        mock_convert.return_value = "/tmp/converted.wav"
        
        for ext in video_extensions:
            mock_check_ext.return_value = ext
            video_file = f"/path/to/video{ext}"
            
            # Mock VIDEO_EXTENSIONS to include the extension
            with patch("app.audio.VIDEO_EXTENSIONS", set(video_extensions)):
                result = process_audio_file(video_file)
            
            mock_convert.assert_called_with(video_file)
            np.testing.assert_array_equal(result, mock_audio_data)


class TestGetAudioDuration:
    """Test cases for get_audio_duration function."""

    @patch("app.audio.SAMPLE_RATE", 16000)
    def test_get_audio_duration_with_16khz(self):
        """Test getting audio duration with 16kHz sample rate."""
        # Create mock audio array (1 second of audio at 16kHz)
        audio = np.zeros(16000)
        
        duration = get_audio_duration(audio)
        
        assert duration == 1.0

    @patch("app.audio.SAMPLE_RATE", 16000)
    def test_get_audio_duration_with_half_second(self):
        """Test getting audio duration for half second audio."""
        # Create mock audio array (0.5 seconds of audio at 16kHz)
        audio = np.zeros(8000)
        
        duration = get_audio_duration(audio)
        
        assert duration == 0.5

    @patch("app.audio.SAMPLE_RATE", 16000)
    def test_get_audio_duration_with_two_seconds(self):
        """Test getting audio duration for two seconds of audio."""
        # Create mock audio array (2 seconds of audio at 16kHz)
        audio = np.zeros(32000)
        
        duration = get_audio_duration(audio)
        
        assert duration == 2.0

    @patch("app.audio.SAMPLE_RATE", 22050)
    def test_get_audio_duration_with_different_sample_rate(self):
        """Test getting audio duration with different sample rate."""
        # Create mock audio array (1 second of audio at 22050Hz)
        audio = np.zeros(22050)
        
        duration = get_audio_duration(audio)
        
        assert duration == 1.0

    @patch("app.audio.SAMPLE_RATE", 16000)
    def test_get_audio_duration_with_empty_audio(self):
        """Test getting audio duration for empty audio."""
        audio = np.zeros(0)
        
        duration = get_audio_duration(audio)
        
        assert duration == 0.0

    @patch("app.audio.SAMPLE_RATE", 16000)
    def test_get_audio_duration_with_realistic_audio_data(self):
        """Test getting audio duration with realistic audio data."""
        # Create realistic audio data (random values between -1 and 1)
        np.random.seed(42)  # For reproducible tests
        audio = np.random.uniform(-1, 1, 48000)  # 3 seconds at 16kHz
        
        duration = get_audio_duration(audio)
        
        assert duration == 3.0

    @patch("app.audio.SAMPLE_RATE", 16000)
    def test_get_audio_duration_precision(self):
        """Test audio duration calculation precision."""
        # Test with non-round number of samples
        audio = np.zeros(16001)  # Slightly more than 1 second
        
        duration = get_audio_duration(audio)
        
        # Should be 16001/16000 = 1.0000625
        expected_duration = 16001 / 16000
        assert abs(duration - expected_duration) < 1e-10