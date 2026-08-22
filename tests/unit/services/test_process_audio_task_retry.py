"""Retry behaviour of the background task runner."""

import os
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings
from app.core.exceptions import (
    AudioProcessingError,
    DatabaseOperationError,
    InsufficientMemoryError,
)
from app.schemas import TaskStatus
from app.services import audio_processing_service

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


class _Harness:
    """Captures repository writes and sleeps for one runner invocation."""

    def __init__(self) -> None:
        """Initialise empty capture buffers."""
        self.updates: list[dict[str, Any]] = []
        self.sleeps: list[float] = []
        self.events: list[str] = []

    @property
    def statuses(self) -> list[Any]:
        """Return the status value of every recorded update."""
        return [u["status"] for u in self.updates if "status" in u]

    def final_update(self) -> dict[str, Any]:
        """Return the last recorded update."""
        return self.updates[-1]


def _run(
    harness: _Harness,
    processor: Any,
    *,
    use_gpu_semaphore: bool = False,
    max_retries: str | None = None,
    backoff: str = "0.01",
    fail_update_on: Any = None,
) -> None:
    """Invoke the runner with the repository, semaphore and sleep patched out.

    Args:
        harness: Capture buffers for updates, sleeps and semaphore events.
        processor: The audio processor callable under test.
        use_gpu_semaphore: Whether the runner should take a GPU slot.
        max_retries: Value for ``TASK_MAX_RETRIES``.
        backoff: Value for ``TASK_RETRY_BACKOFF_SECONDS``.
        fail_update_on: Status whose repository write should raise, simulating
            a database outage during bookkeeping.
    """
    if max_retries is not None:
        os.environ["TASK_MAX_RETRIES"] = max_retries
    os.environ["TASK_RETRY_BACKOFF_SECONDS"] = backoff
    get_settings.cache_clear()

    def record(identifier: str, update_data: dict[str, Any]) -> None:
        harness.updates.append(update_data)
        if fail_update_on is not None and update_data.get("status") == fail_update_on:
            raise DatabaseOperationError("update", "database is locked")

    repository = MagicMock()
    repository.update.side_effect = record

    semaphore = MagicMock()
    semaphore.acquire.side_effect = lambda: harness.events.append("acquire")
    semaphore.release.side_effect = lambda: harness.events.append("release")

    def fake_sleep(seconds: float) -> None:
        harness.sleeps.append(seconds)
        harness.events.append("sleep")

    with (
        patch.object(audio_processing_service, "SyncSessionLocal", MagicMock()),
        patch.object(
            audio_processing_service,
            "SyncSQLAlchemyTaskRepository",
            return_value=repository,
        ),
        patch.object(audio_processing_service.time, "sleep", fake_sleep),
        patch(
            "app.core.gpu_semaphore.get_gpu_semaphore",
            return_value=semaphore,
        ),
    ):
        audio_processing_service.process_audio_task(
            audio_processor=processor,
            identifier="task-1",
            task_type="transcription",
            use_gpu_semaphore=use_gpu_semaphore,
        )


@pytest.mark.unit
def test_success_on_first_attempt_runs_once() -> None:
    """The happy path is unchanged: one attempt, task completed."""
    harness = _Harness()
    processor = MagicMock(return_value={"text": "ok"})

    _run(harness, processor, max_retries="2")

    assert processor.call_count == 1
    assert harness.final_update()["status"] == TaskStatus.completed
    assert harness.sleeps == []


@pytest.mark.unit
def test_no_retry_when_disabled() -> None:
    """With the default configuration a transient failure is still final."""
    harness = _Harness()
    processor = MagicMock(side_effect=InsufficientMemoryError("transcription"))

    _run(harness, processor, max_retries="0")

    assert processor.call_count == 1
    assert harness.final_update()["status"] == TaskStatus.failed
    assert harness.final_update()["retry_count"] == 0


@pytest.mark.unit
def test_transient_failure_is_retried_until_it_succeeds() -> None:
    """A task that fails transiently then succeeds ends up completed."""
    harness = _Harness()
    processor = MagicMock(
        side_effect=[InsufficientMemoryError("transcription"), {"text": "ok"}]
    )

    _run(harness, processor, max_retries="2")

    assert processor.call_count == 2
    assert harness.final_update()["status"] == TaskStatus.completed
    # The error from the failed attempt must not linger on a completed task.
    assert harness.final_update()["error"] is None
    assert TaskStatus.queued in harness.statuses


@pytest.mark.unit
def test_retries_are_exhausted_then_task_fails() -> None:
    """After the budget is spent the task is marked failed with the count."""
    harness = _Harness()
    processor = MagicMock(side_effect=InsufficientMemoryError("transcription"))

    _run(harness, processor, max_retries="2")

    assert processor.call_count == 3  # initial attempt plus two retries
    final = harness.final_update()
    assert final["status"] == TaskStatus.failed
    assert final["retry_count"] == 2


@pytest.mark.unit
def test_deterministic_failure_is_not_retried() -> None:
    """A corrupt file fails once, even with retries enabled."""
    harness = _Harness()
    processor = MagicMock(side_effect=AudioProcessingError("file is corrupt"))

    _run(harness, processor, max_retries="3")

    assert processor.call_count == 1
    assert harness.final_update()["status"] == TaskStatus.failed
    assert harness.sleeps == []


@pytest.mark.unit
def test_backoff_is_applied_between_attempts() -> None:
    """The runner waits between attempts, doubling each time."""
    harness = _Harness()
    processor = MagicMock(side_effect=InsufficientMemoryError("transcription"))

    _run(harness, processor, max_retries="2", backoff="1")

    assert harness.sleeps == [1.0, 2.0]


@pytest.mark.unit
def test_gpu_slot_is_released_before_sleeping() -> None:
    """Backoff must never happen while the GPU semaphore is held.

    Sleeping with the slot held would block every other queued task for the
    whole backoff period, which is the opposite of what retrying is for.
    """
    harness = _Harness()
    processor = MagicMock(
        side_effect=[InsufficientMemoryError("transcription"), {"text": "ok"}]
    )

    _run(harness, processor, use_gpu_semaphore=True, max_retries="1")

    assert harness.events == [
        "acquire",
        "release",
        "sleep",
        "acquire",
        "release",
    ]


@pytest.mark.unit
def test_gpu_slot_released_once_per_attempt() -> None:
    """Every acquire is matched by exactly one release across all attempts."""
    harness = _Harness()
    processor = MagicMock(side_effect=InsufficientMemoryError("transcription"))

    _run(harness, processor, use_gpu_semaphore=True, max_retries="2")

    assert harness.events.count("acquire") == 3
    assert harness.events.count("release") == 3


@pytest.mark.unit
def test_retry_survives_a_failed_requeue_write() -> None:
    """A database blip while recording the retry must not cancel the retry.

    DatabaseOperationError is itself retryable, so the bookkeeping write that
    marks a task queued can fail for precisely the reason the task is being
    retried. If that write escaped the handler, the retry loop would die on the
    very class of failure it exists to survive.
    """
    harness = _Harness()
    processor = MagicMock(
        side_effect=[InsufficientMemoryError("transcription"), {"text": "ok"}]
    )

    _run(harness, processor, max_retries="2", fail_update_on=TaskStatus.queued)

    # The retry still happened despite the requeue write blowing up.
    assert processor.call_count == 2
    assert harness.final_update()["status"] == TaskStatus.completed
