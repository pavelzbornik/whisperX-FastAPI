"""Route-level concurrency gates for GPU-bound request paths.

These gates are separate from the GPU ``threading.Semaphore`` (which protects
VRAM). They cap how many GPU-bound requests may be in flight per path so the
anyio threadpool and connection slots are not exhausted, and so synchronous
(OpenAI-compatible) traffic and asynchronous background traffic each receive a
guaranteed share of the overall budget rather than starving one another.

The total budget is ``MAX_QUEUED_GPU_REQUESTS`` split by
``SYNC_GPU_QUOTA_FRACTION``. A total of ``0`` means unlimited (no-op), which is
the default so existing deployments are unaffected.
"""

import threading
from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import logger


class ConcurrencyGate:
    """A non-blocking concurrency limiter.

    A capacity of ``0`` means unlimited and the gate becomes a no-op:
    :meth:`acquire` always succeeds and :meth:`release` does nothing.
    """

    def __init__(self, capacity: int) -> None:
        """Initialise the gate.

        Args:
            capacity: Maximum number of simultaneous holders, or 0 for unlimited.
        """
        self._capacity = capacity
        self._semaphore = threading.BoundedSemaphore(capacity) if capacity > 0 else None

    @property
    def capacity(self) -> int:
        """Return the configured slot count, where 0 means unlimited."""
        return self._capacity

    def acquire(self) -> bool:
        """Try to acquire a slot without blocking.

        Returns:
            True if a slot was acquired (or the gate is unlimited), else False.
        """
        if self._semaphore is None:
            return True
        return self._semaphore.acquire(blocking=False)

    def release(self) -> None:
        """Release a previously acquired slot (no-op when unlimited)."""
        if self._semaphore is not None:
            self._semaphore.release()


def compute_quota_split(total: int, sync_fraction: float) -> tuple[int, int]:
    """Split a total budget into ``(sync_capacity, async_capacity)``.

    A ``total`` of 0 (or less) yields ``(0, 0)`` meaning both paths are
    unlimited. For ``total >= 2`` the split is exact
    (``sync + async == total``) and each path is guaranteed at least one
    slot, so a fraction of 0 or 1 cannot lock out either path.

    ``total == 1`` is rejected by the Settings validator (it cannot be
    split without either exceeding the cap or closing one path); callers
    should not pass it here.

    Args:
        total: The overall concurrent-request budget.
        sync_fraction: Fraction of the budget reserved for the sync path.

    Returns:
        Tuple of (sync capacity, async capacity).
    """
    if total <= 0:
        return 0, 0
    # Clamp the sync share to [1, total - 1] so the async path keeps >= 1 slot
    # and the two shares always sum to exactly ``total``.
    sync_capacity = min(max(round(total * sync_fraction), 1), total - 1)
    return sync_capacity, total - sync_capacity


@lru_cache(maxsize=1)
def get_sync_concurrency_gate() -> ConcurrencyGate:
    """Return the shared concurrency gate for the synchronous request path."""
    settings = get_settings()
    sync_capacity, _ = compute_quota_split(
        settings.MAX_QUEUED_GPU_REQUESTS, settings.SYNC_GPU_QUOTA_FRACTION
    )
    logger.info("Sync GPU concurrency gate initialized with capacity=%d", sync_capacity)
    return ConcurrencyGate(sync_capacity)


@lru_cache(maxsize=1)
def get_async_concurrency_gate() -> ConcurrencyGate:
    """Return the shared concurrency gate for the asynchronous request path."""
    settings = get_settings()
    _, async_capacity = compute_quota_split(
        settings.MAX_QUEUED_GPU_REQUESTS, settings.SYNC_GPU_QUOTA_FRACTION
    )
    logger.info(
        "Async GPU concurrency gate initialized with capacity=%d", async_capacity
    )
    return ConcurrencyGate(async_capacity)
