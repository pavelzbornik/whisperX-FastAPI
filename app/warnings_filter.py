"""This module filters specific warnings from various libraries used in the project."""

import warnings

# from pyannote.audio import ReproducibilityWarning


def filter_warnings():
    """Filter specific warnings from various libraries used in the project."""
    # Filter specific torchaudio deprecation warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")
    warnings.filterwarnings("ignore", category=UserWarning, module="pyannote.audio")
    warnings.filterwarnings("ignore", category=UserWarning, module="speechbrain")
    warnings.filterwarnings(
        "ignore", category=UserWarning, module="asteroid_filterbanks"
    )
    warnings.filterwarnings(
        "ignore", message="torchaudio._backend.set_audio_backend has been deprecated*"
    )
    warnings.filterwarnings(
        "ignore", message="torchaudio._backend.get_audio_backend has been deprecated*"
    )
    warnings.filterwarnings(
        "ignore", message="Module 'speechbrain.pretrained' was deprecated*"
    )
    warnings.filterwarnings(
        "ignore",
        message="`torchaudio.backend.common.AudioMetaData` has been moved to `torchaudio.AudioMetaData`*",
    )
    warnings.filterwarnings(
        "ignore", message="Lightning automatically upgraded your loaded checkpoint*"
    )
    warnings.filterwarnings("ignore", message="Model was trained*")
    # warnings.filterwarnings("ignore", category=ReproducibilityWarning, module="pyannote.audio")
    warnings.filterwarnings("ignore", category=FutureWarning, module="huggingface_hub")
    warnings.filterwarnings(
        "ignore", message="Special tokens have been added in the vocabulary*"
    )
    warnings.filterwarnings("ignore", message="Applied workaround for CuDNN issue*")
    warnings.filterwarnings(
        "ignore",
        message="Applied quirks (see `speechbrain.utils.quirks`): [allow_tf32, disable_jit_profiling]",
    )
    warnings.filterwarnings("ignore", message="Excluded quirks specified by the *")
