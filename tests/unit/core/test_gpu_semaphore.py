"""Unit tests for GPU semaphore module."""

import threading
from unittest.mock import MagicMock, patch

import pytest

from app.core.gpu_semaphore import get_gpu_semaphore


@pytest.mark.unit
class TestGpuSemaphore:
    """Unit tests for get_gpu_semaphore."""

    def setup_method(self) -> None:
        """Clear the lru_cache before each test."""
        get_gpu_semaphore.cache_clear()

    def teardown_method(self) -> None:
        """Clear the lru_cache after each test."""
        get_gpu_semaphore.cache_clear()

    @patch("app.core.gpu_semaphore.get_settings")
    def test_returns_semaphore_instance(self, mock_get_settings: MagicMock) -> None:
        """Test get_gpu_semaphore returns a threading.Semaphore."""
        mock_get_settings.return_value = MagicMock(MAX_CONCURRENT_GPU_TASKS=2)
        sem = get_gpu_semaphore()
        assert isinstance(sem, threading.Semaphore)

    @patch("app.core.gpu_semaphore.get_settings")
    def test_singleton_returns_same_instance(
        self, mock_get_settings: MagicMock
    ) -> None:
        """Test get_gpu_semaphore returns the same instance on repeated calls."""
        mock_get_settings.return_value = MagicMock(MAX_CONCURRENT_GPU_TASKS=1)
        sem1 = get_gpu_semaphore()
        sem2 = get_gpu_semaphore()
        assert sem1 is sem2

    @patch("app.core.gpu_semaphore.get_settings")
    def test_initialized_with_correct_value(self, mock_get_settings: MagicMock) -> None:
        """Test semaphore is initialized with MAX_CONCURRENT_GPU_TASKS value."""
        mock_get_settings.return_value = MagicMock(MAX_CONCURRENT_GPU_TASKS=3)
        sem = get_gpu_semaphore()

        # Should be able to acquire 3 times without blocking
        for _ in range(3):
            assert sem.acquire(blocking=False)

        # 4th acquire should fail (non-blocking)
        assert not sem.acquire(blocking=False)

        # Release all
        for _ in range(3):
            sem.release()

    @patch("app.core.gpu_semaphore.get_settings")
    def test_default_value_of_one(self, mock_get_settings: MagicMock) -> None:
        """Test semaphore with default value of 1 allows only one concurrent task."""
        mock_get_settings.return_value = MagicMock(MAX_CONCURRENT_GPU_TASKS=1)
        sem = get_gpu_semaphore()

        assert sem.acquire(blocking=False)
        assert not sem.acquire(blocking=False)
        sem.release()
