"""GPU concurrency control via a shared threading semaphore."""

import threading
from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import logger


@lru_cache(maxsize=1)
def get_gpu_semaphore() -> threading.Semaphore:
    """Return the shared GPU semaphore (singleton).

    The semaphore limits concurrent GPU-heavy tasks to prevent CUDA OOM errors.
    Initialized lazily on first call using MAX_CONCURRENT_GPU_TASKS from settings.
    """
    settings = get_settings()
    max_tasks = settings.MAX_CONCURRENT_GPU_TASKS
    logger.info("GPU semaphore initialized with max_concurrent_gpu_tasks=%d", max_tasks)
    return threading.Semaphore(max_tasks)
