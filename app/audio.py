"""This module provides functions for processing audio files."""

import subprocess
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np
from whisperx import load_audio
from whisperx.audio import SAMPLE_RATE

from app.files import VIDEO_EXTENSIONS, check_file_extension


def convert_video_to_audio(file: str) -> str:
    """
    Convert a video file to an audio file.

    Args:
        file (str): The path to the video file.

    Returns:
        str: The path to the audio file.
    """
    temp_filename = NamedTemporaryFile(delete=False).name
    subprocess.call(
        [
            "ffmpeg",
            "-y",  # Overwrite output file if it exists"
            "-i",
            file,
            "-vn",
            "-ac",
            "1",  # Mono audio
            "-ar",
            "16000",  # Sample rate of 16kHz
            "-f",
            "wav",  # Output format WAV
            temp_filename,
        ]
    )
    return temp_filename


def process_audio_file(audio_file: str) -> np.ndarray[Any, np.dtype[np.float32]]:
    """
    Check file if it is audio file, if it is video file, convert it to audio file.

    Args:
        audio_file (str): The path to the audio file.
    Returns:
        Audio: The processed audio.
    """
    file_extension = check_file_extension(audio_file)
    if file_extension in VIDEO_EXTENSIONS:
        audio_file = convert_video_to_audio(audio_file)
    return load_audio(audio_file)  # type: ignore[no-any-return]


def get_audio_duration(audio: np.ndarray[Any, np.dtype[np.float32]]) -> float:
    """
    Get the duration of the audio file.

    Args:
        audio_file (str): The path to the audio file.
    Returns:
        float: The duration of the audio file.
    """
    return len(audio) / SAMPLE_RATE  # type: ignore[no-any-return]
