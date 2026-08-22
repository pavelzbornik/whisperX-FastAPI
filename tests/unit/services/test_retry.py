"""Unit tests for the background-task retry policy."""

import os
from collections.abc import Generator

import pytest

from app.core.config import get_settings
from app.core.exceptions import (
    AudioProcessingError,
    ConfigurationError,
    DatabaseOperationError,
    FileDownloadError,
    InsufficientMemoryError,
    ModelLoadError,
    UnsupportedFileExtensionError,
    ValidationError,
)
from app.services.retry import RetryPolicy, is_retryable

_ENV_KEYS = ("TASK_MAX_RETRIES", "TASK_RETRY_BACKOFF_SECONDS")


@pytest.fixture(autouse=True)
def reset_retry_env() -> Generator[None, None, None]:
    """Restore retry env vars and the settings cache around each test."""
    get_settings.cache_clear()
    originals = {key: os.environ.get(key) for key in _ENV_KEYS}
    yield
    for key, value in originals.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


def _policy(**env: str) -> RetryPolicy:
    """Build a policy from the given env overrides."""
    for key, value in env.items():
        os.environ[key] = value
    get_settings.cache_clear()
    return RetryPolicy.from_settings()


# --------------------------------------------------------------------------
# Which failures are worth retrying
# --------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "exc",
    [
        InsufficientMemoryError("transcription"),
        ModelLoadError("tiny"),
        FileDownloadError("http://example.com/a.wav"),
        DatabaseOperationError("insert", "deadlock"),
        MemoryError("out of memory"),
        RuntimeError("CUDA out of memory"),
        TimeoutError("timed out"),
        ConnectionError("connection reset"),
    ],
)
def test_transient_failures_are_retryable(exc: BaseException) -> None:
    """Infrastructure and resource failures may succeed on a later attempt."""
    assert is_retryable(exc) is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "exc",
    [
        ValidationError("bad input"),
        UnsupportedFileExtensionError("a.xyz", ".xyz", {".wav"}),
        AudioProcessingError("file is corrupt"),
        ConfigurationError("HF_TOKEN missing"),
        ValueError("bad value"),
        TypeError("bad type"),
        KeyError("missing"),
    ],
)
def test_deterministic_failures_are_not_retryable(exc: BaseException) -> None:
    """A failure caused by the input or the config will fail again identically.

    Retrying these burns GPU time for a guaranteed second failure.
    """
    assert is_retryable(exc) is False


@pytest.mark.unit
def test_unknown_exceptions_are_not_retried() -> None:
    """An unrecognised failure is treated as deterministic.

    Conservative on purpose: a repeatable bug should not consume the whole
    retry budget on every task.
    """

    class SomethingUnexpected(Exception):
        pass

    assert is_retryable(SomethingUnexpected("?")) is False


# --------------------------------------------------------------------------
# Policy configuration
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_retries_are_disabled_by_default() -> None:
    """Retry is opt-in, so existing deployments behave exactly as before."""
    os.environ.pop("TASK_MAX_RETRIES", None)
    get_settings.cache_clear()

    policy = RetryPolicy.from_settings()

    assert policy.max_retries == 0
    assert policy.enabled is False
    assert policy.max_attempts == 1


@pytest.mark.unit
def test_enabled_policy_allows_one_attempt_more_than_retries() -> None:
    """Two retries means three total attempts."""
    policy = _policy(TASK_MAX_RETRIES="2")

    assert policy.enabled is True
    assert policy.max_attempts == 3


@pytest.mark.unit
def test_should_retry_requires_budget_and_a_transient_error() -> None:
    """Both conditions must hold — budget alone is not enough."""
    policy = _policy(TASK_MAX_RETRIES="2")

    assert policy.should_retry(MemoryError(), attempt=1) is True
    assert policy.should_retry(MemoryError(), attempt=2) is True
    # Third attempt is the last one allowed, so no further retry.
    assert policy.should_retry(MemoryError(), attempt=3) is False
    # Budget remains, but the failure will repeat.
    assert policy.should_retry(ValueError(), attempt=1) is False


@pytest.mark.unit
def test_disabled_policy_never_retries() -> None:
    """With retries off, even a transient failure is final."""
    policy = _policy(TASK_MAX_RETRIES="0")

    assert policy.should_retry(MemoryError(), attempt=1) is False


@pytest.mark.unit
def test_backoff_grows_exponentially() -> None:
    """Each attempt waits longer, so a struggling GPU gets time to recover."""
    policy = _policy(TASK_MAX_RETRIES="4", TASK_RETRY_BACKOFF_SECONDS="2")

    assert policy.delay_for(attempt=1) == 2.0
    assert policy.delay_for(attempt=2) == 4.0
    assert policy.delay_for(attempt=3) == 8.0


@pytest.mark.unit
def test_backoff_is_capped() -> None:
    """Backoff cannot grow without bound on a long retry budget."""
    policy = _policy(TASK_MAX_RETRIES="10", TASK_RETRY_BACKOFF_SECONDS="30")

    assert policy.delay_for(attempt=9) <= RetryPolicy.MAX_DELAY_SECONDS


@pytest.mark.unit
def test_negative_retry_count_is_rejected() -> None:
    """A nonsensical configuration fails at startup rather than silently."""
    with pytest.raises(ValueError):
        _policy(TASK_MAX_RETRIES="-1")
