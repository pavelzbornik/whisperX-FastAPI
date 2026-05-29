"""Unit tests for security dependencies (auth + concurrency gates)."""

import os
from collections.abc import AsyncGenerator, Generator

import pytest

from app.api.security import (
    enforce_async_gpu_quota,
    enforce_sync_gpu_quota,
    verify_bearer_token,
)
from app.core.concurrency import (
    get_async_concurrency_gate,
    get_sync_concurrency_gate,
)
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ServiceOverloadedError


@pytest.fixture
def reset_auth_env() -> Generator[None, None, None]:
    """Snapshot and restore AUTH__ env vars around each test."""
    saved = {
        key: os.environ.get(key) for key in ("AUTH__ENABLED", "AUTH__BEARER_TOKEN")
    }
    get_settings.cache_clear()
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


@pytest.fixture
def reset_gate_env() -> Generator[None, None, None]:
    """Snapshot/restore queue cap env and clear cached gates around each test."""
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
def test_auth_disabled_is_noop(reset_auth_env: None) -> None:
    """When auth is disabled, any (or no) credential is accepted."""
    os.environ.pop("AUTH__ENABLED", None)
    get_settings.cache_clear()

    assert verify_bearer_token(None) is None
    assert verify_bearer_token("Bearer anything") is None


@pytest.mark.unit
def test_auth_enabled_accepts_valid_token(reset_auth_env: None) -> None:
    """A matching bearer token passes when auth is enabled."""
    os.environ["AUTH__ENABLED"] = "true"
    os.environ["AUTH__BEARER_TOKEN"] = "s3cret"
    get_settings.cache_clear()

    assert verify_bearer_token("Bearer s3cret") is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "header",
    [None, "", "Token s3cret", "Bearer", "Bearer wrong"],
)
def test_auth_enabled_rejects_bad_token(
    reset_auth_env: None, header: str | None
) -> None:
    """Missing or non-matching credentials are rejected with 401 semantics."""
    os.environ["AUTH__ENABLED"] = "true"
    os.environ["AUTH__BEARER_TOKEN"] = "s3cret"
    get_settings.cache_clear()

    with pytest.raises(AuthenticationError):
        verify_bearer_token(header)


async def _drain(gen: AsyncGenerator[None, None]) -> None:
    """Acquire then release a concurrency-gate dependency generator."""
    await gen.__anext__()
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()


@pytest.mark.unit
async def test_sync_quota_releases_slot(reset_gate_env: None) -> None:
    """The sync dependency acquires and then releases its slot."""
    os.environ["MAX_QUEUED_GPU_REQUESTS"] = "2"
    os.environ["SYNC_GPU_QUOTA_FRACTION"] = "0.5"
    get_settings.cache_clear()
    get_sync_concurrency_gate.cache_clear()
    get_async_concurrency_gate.cache_clear()

    await _drain(enforce_sync_gpu_quota())
    # Slot was released, so the gate is fully available again.
    gate = get_sync_concurrency_gate()
    assert gate.acquire() is True
    gate.release()


@pytest.mark.unit
async def test_sync_quota_rejects_when_full(reset_gate_env: None) -> None:
    """The sync dependency raises 503 when no slot is available."""
    os.environ["MAX_QUEUED_GPU_REQUESTS"] = "2"
    os.environ["SYNC_GPU_QUOTA_FRACTION"] = "0.5"
    get_settings.cache_clear()
    get_sync_concurrency_gate.cache_clear()
    get_async_concurrency_gate.cache_clear()

    gate = get_sync_concurrency_gate()  # capacity 1
    assert gate.acquire() is True  # exhaust the only slot

    gen = enforce_sync_gpu_quota()
    with pytest.raises(ServiceOverloadedError):
        await gen.__anext__()
    gate.release()


@pytest.mark.unit
async def test_async_quota_rejects_when_full(reset_gate_env: None) -> None:
    """The async dependency raises 503 when no slot is available."""
    os.environ["MAX_QUEUED_GPU_REQUESTS"] = "2"
    os.environ["SYNC_GPU_QUOTA_FRACTION"] = "0.5"
    get_settings.cache_clear()
    get_sync_concurrency_gate.cache_clear()
    get_async_concurrency_gate.cache_clear()

    gate = get_async_concurrency_gate()  # capacity 1
    assert gate.acquire() is True

    gen = enforce_async_gpu_quota()
    with pytest.raises(ServiceOverloadedError):
        await gen.__anext__()
    gate.release()
