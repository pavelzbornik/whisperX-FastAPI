"""Unit tests for route-level concurrency gates."""

import os
from collections.abc import Generator

import pytest

from app.core.concurrency import (
    ConcurrencyGate,
    compute_quota_split,
    get_async_concurrency_gate,
    get_sync_concurrency_gate,
)
from app.core.config import get_settings


@pytest.fixture
def reset_gates() -> Generator[None, None, None]:
    """Clear cached gates and quota env vars around each test."""
    saved = {
        key: os.environ.get(key)
        for key in ("MAX_QUEUED_GPU_REQUESTS", "SYNC_GPU_QUOTA_FRACTION")
    }
    get_settings.cache_clear()
    get_sync_concurrency_gate.cache_clear()
    get_async_concurrency_gate.cache_clear()
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()
    get_sync_concurrency_gate.cache_clear()
    get_async_concurrency_gate.cache_clear()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("total", "fraction", "expected"),
    [
        (0, 0.5, (0, 0)),
        (20, 0.5, (10, 10)),
        (20, 0.25, (5, 15)),
        (10, 0.0, (1, 9)),
        (10, 1.0, (9, 1)),
        (2, 0.5, (1, 1)),
    ],
)
def test_compute_quota_split(
    total: int, fraction: float, expected: tuple[int, int]
) -> None:
    """For total>=2 the split is exact and each path keeps >=1 slot."""
    assert compute_quota_split(total, fraction) == expected


@pytest.mark.unit
def test_compute_quota_split_never_exceeds_total_when_capped() -> None:
    """For any total>=2, the two shares sum to exactly the configured total."""
    for total in range(2, 33):
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            sync, async_ = compute_quota_split(total, fraction)
            assert sync >= 1 and async_ >= 1
            assert sync + async_ == total


@pytest.mark.unit
def test_unlimited_gate_is_no_op() -> None:
    """A capacity of 0 always grants acquisition."""
    gate = ConcurrencyGate(0)
    assert gate.capacity == 0
    assert gate.acquire() is True
    assert gate.acquire() is True
    gate.release()  # must not raise


@pytest.mark.unit
def test_gate_blocks_when_exhausted() -> None:
    """A capped gate rejects acquisition once full and recovers on release."""
    gate = ConcurrencyGate(1)
    assert gate.acquire() is True
    assert gate.acquire() is False
    gate.release()
    assert gate.acquire() is True


@pytest.mark.unit
def test_gates_sized_from_settings(reset_gates: None) -> None:
    """Cached gates pick up their capacity from settings."""
    os.environ["MAX_QUEUED_GPU_REQUESTS"] = "4"
    os.environ["SYNC_GPU_QUOTA_FRACTION"] = "0.5"
    get_settings.cache_clear()
    get_sync_concurrency_gate.cache_clear()
    get_async_concurrency_gate.cache_clear()

    assert get_sync_concurrency_gate().capacity == 2
    assert get_async_concurrency_gate().capacity == 2


@pytest.mark.unit
def test_gates_unlimited_by_default(reset_gates: None) -> None:
    """With the default cap of 0 both gates are unlimited."""
    os.environ.pop("MAX_QUEUED_GPU_REQUESTS", None)
    get_settings.cache_clear()
    get_sync_concurrency_gate.cache_clear()
    get_async_concurrency_gate.cache_clear()

    assert get_sync_concurrency_gate().capacity == 0
    assert get_async_concurrency_gate().capacity == 0
