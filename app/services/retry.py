"""Retry policy for background tasks.

A transcription job can fail for two very different reasons. Some failures are
properties of the input — a corrupt file, an unsupported extension, a bad
parameter — and will fail identically however often they are repeated. Others
are properties of the moment: the GPU was full, a model download was cut off, a
database deadlock. Only the second kind is worth another attempt, because
retrying the first kind spends GPU time to reach the same conclusion.

Retrying is opt-in (``TASK_MAX_RETRIES`` defaults to 0), so existing
deployments keep their current behaviour until they ask for it.
"""

import logging
from dataclasses import dataclass
from typing import ClassVar

from app.core.config import get_settings
from app.core.exceptions import InfrastructureError

logger = logging.getLogger(__name__)

# Failures that plausibly resolve themselves on a later attempt.
#
# InfrastructureError covers the application's own transient categories —
# ModelLoadError, FileDownloadError, InsufficientMemoryError,
# DatabaseOperationError. The builtins cover what escapes from torch and the
# HTTP stack: CUDA reports out-of-memory as a RuntimeError, and MemoryError
# means another task was holding the memory this one needed.
RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    InfrastructureError,
    MemoryError,
    RuntimeError,
    TimeoutError,
    ConnectionError,
)


def is_retryable(exc: BaseException) -> bool:
    """Report whether *exc* is worth another attempt.

    Anything not explicitly listed as transient is treated as deterministic.
    That is deliberately conservative: an unrecognised failure is more likely a
    repeatable bug than a passing glitch, and burning the retry budget on every
    such task would multiply GPU cost for nothing.

    Args:
        exc: The exception raised by the task.

    Returns:
        ``True`` when the task may be retried.
    """
    return isinstance(exc, RETRYABLE_EXCEPTIONS)


@dataclass(frozen=True)
class RetryPolicy:
    """How often, and how patiently, a failed task is retried."""

    max_retries: int
    backoff_seconds: float

    # ClassVar, not a field: this is a constant, and a plain annotation would
    # make it a third constructor argument on the dataclass.
    #
    # Without a ceiling, a large budget and a large base delay would leave a
    # task asleep for hours while holding a worker thread.
    MAX_DELAY_SECONDS: ClassVar[float] = 300.0

    @classmethod
    def from_settings(cls) -> "RetryPolicy":
        """Build the policy from application settings.

        Returns:
            Policy reflecting ``TASK_MAX_RETRIES`` and
            ``TASK_RETRY_BACKOFF_SECONDS``.
        """
        settings = get_settings()
        return cls(
            max_retries=settings.TASK_MAX_RETRIES,
            backoff_seconds=settings.TASK_RETRY_BACKOFF_SECONDS,
        )

    @property
    def enabled(self) -> bool:
        """Report whether retrying is switched on at all."""
        return self.max_retries > 0

    @property
    def max_attempts(self) -> int:
        """Return the total number of attempts, including the first."""
        return self.max_retries + 1

    def should_retry(self, exc: BaseException, attempt: int) -> bool:
        """Decide whether to make another attempt after *exc*.

        Args:
            exc: The exception raised by the attempt that just failed.
            attempt: 1-based number of the attempt that just failed.

        Returns:
            ``True`` when budget remains and the failure looks transient.
        """
        if not self.enabled or attempt >= self.max_attempts:
            return False
        return is_retryable(exc)

    def delay_for(self, attempt: int) -> float:
        """Return the seconds to wait before the attempt after *attempt*.

        Args:
            attempt: 1-based number of the attempt that just failed.

        Returns:
            Delay in seconds, doubling per attempt and capped at
            ``MAX_DELAY_SECONDS``.
        """
        delay: float = self.backoff_seconds * (2 ** (attempt - 1))
        return min(delay, self.MAX_DELAY_SECONDS)
