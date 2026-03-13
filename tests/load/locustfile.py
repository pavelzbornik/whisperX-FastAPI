"""Locust load test users for the WhisperX-FastAPI service.

Four user classes cover the full request surface:

- ``ReadOnlyUser``   (weight 6) — read-only endpoints, high concurrency baseline
- ``LifecycleUser``  (weight 4) — submit audio → poll until terminal status
- ``CombineUser``    (weight 2) — JSON-only writes, cheapest write path
- ``ErrorProbeUser`` (weight 1) — intentional 404/422s, validates error-path stability

Run all classes (default):
    uv run locust -f tests/load/locustfile.py --host http://localhost:8000

Run a single class::

    uv run locust -f tests/load/locustfile.py ReadOnlyUser \
        --host http://localhost:8000
"""

import random
import time

from locust import HttpUser, between, task

from tests.load import fixtures


class ReadOnlyUser(HttpUser):
    """Simulates users who read task status and health endpoints.

    Collects existing task IDs on start so per-ID polling exercises
    the ``GET /task/{id}`` path against real rows.
    """

    weight = 6
    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        """Seed known task IDs from the current task list."""
        resp = self.client.get("/task/all")
        if resp.status_code == 200:
            tasks = resp.json().get("tasks", [])
            self._known_ids: list[str] = [t["identifier"] for t in tasks]
        else:
            self._known_ids = []

    @task(5)
    def list_tasks(self) -> None:
        """GET /task/all — exercises DB read pool on every request."""
        self.client.get("/task/all")

    @task(3)
    def health_ready(self) -> None:
        """GET /health/ready — DB connectivity check."""
        self.client.get("/health/ready")

    @task(2)
    def health(self) -> None:
        """GET /health — lightweight liveness check, no DB."""
        self.client.get("/health")

    @task(2)
    def poll_known_task(self) -> None:
        """GET /task/{id} — per-ID poll against a real task row."""
        if not self._known_ids:
            # Refresh from the task list in case tasks were created after on_start
            resp = self.client.get("/task/all")
            if resp.status_code == 200:
                self._known_ids = [
                    t["identifier"] for t in resp.json().get("tasks", [])
                ]
            if not self._known_ids:
                return
        identifier = random.choice(self._known_ids)
        self.client.get(f"/task/{identifier}", name="/task/[id]")


class LifecycleUser(HttpUser):
    """Simulates users who submit audio jobs and poll for results.

    Covers the full read-after-write path: POST creates a task row
    immediately, then GET /task/{id} polls until the task reaches a
    terminal status (``completed`` or ``failed``) or the poll cap is hit.

    Background ML tasks will fail quickly in test environments (no models
    loaded), so the poll loop exits in 1-2 iterations in practice.
    """

    weight = 4
    wait_time = between(2, 10)

    @task(1)
    def submit_and_poll(self) -> None:
        """POST /speech-to-text then poll until terminal status."""
        resp = self.client.post(
            "/speech-to-text",
            files={"file": ("audio_en.mp3", fixtures.AUDIO_BYTES, "audio/mpeg")},
            name="/speech-to-text",
        )
        if resp.status_code != 200:
            return
        identifier = resp.json().get("identifier")
        if identifier:
            self._poll_until_terminal(identifier)

    @task(1)
    def submit_transcribe_and_poll(self) -> None:
        """POST /service/transcribe then poll until terminal status."""
        resp = self.client.post(
            "/service/transcribe",
            files={"file": ("audio_en.mp3", fixtures.AUDIO_BYTES, "audio/mpeg")},
            name="/service/transcribe",
        )
        if resp.status_code != 200:
            return
        identifier = resp.json().get("identifier")
        if identifier:
            self._poll_until_terminal(identifier)

    def _poll_until_terminal(self, identifier: str, max_polls: int = 5) -> None:
        """Poll GET /task/{id} until terminal status or poll cap.

        All per-ID requests are grouped under the name ``/task/[id]`` so
        locust stats stay readable regardless of how many unique IDs exist.

        Args:
            identifier: Task UUID to poll.
            max_polls: Maximum number of poll attempts before giving up.
        """
        for _ in range(max_polls):
            resp = self.client.get(f"/task/{identifier}", name="/task/[id]")
            if resp.status_code != 200:
                break
            if resp.json().get("status") in ("completed", "failed"):
                break
            time.sleep(2)


class CombineUser(HttpUser):
    """Simulates users calling the JSON-only combine service.

    ``POST /service/combine`` accepts two JSON files (no audio parsing),
    making it the cheapest write endpoint to run at volume. Used to stress
    the DB write path without the overhead of audio file processing.
    """

    weight = 2
    wait_time = between(1, 4)

    @task(3)
    def submit_combine(self) -> None:
        """POST /service/combine then immediately poll once."""
        resp = self.client.post(
            "/service/combine",
            files={
                "aligned_transcript": (
                    "aligned_transcript.json",
                    fixtures.ALIGNED_TRANSCRIPT_BYTES,
                    "application/json",
                ),
                "diarization_result": (
                    "diarization.json",
                    fixtures.DIARIZATION_BYTES,
                    "application/json",
                ),
            },
            name="/service/combine",
        )
        if resp.status_code == 200:
            identifier = resp.json().get("identifier")
            if identifier:
                # Single immediate poll — validates read-after-write consistency
                self.client.get(f"/task/{identifier}", name="/task/[id]")

    @task(1)
    def list_tasks(self) -> None:
        """GET /task/all — mixes reads with the write workload."""
        self.client.get("/task/all")


class ErrorProbeUser(HttpUser):
    """Simulates malformed or invalid requests.

    Validates that error-handling paths (404, 422) remain stable and fast
    under concurrent load. Uses ``catch_response=True`` so expected non-2xx
    responses are recorded as successes in locust stats.
    """

    weight = 1
    wait_time = between(1, 3)

    @task(3)
    def poll_nonexistent_task(self) -> None:
        """GET /task/{nonexistent} — expects 404."""
        with self.client.get(
            "/task/load-test-nonexistent-000",
            name="/task/[404]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 404:
                resp.success()
            else:
                resp.failure(f"Expected 404, got {resp.status_code}")

    @task(2)
    def upload_invalid_extension(self) -> None:
        """POST /speech-to-text with wrong file type — expects 400/422."""
        with self.client.post(
            "/speech-to-text",
            files={"file": ("malicious.exe", b"not-audio", "application/octet-stream")},
            name="/speech-to-text [invalid ext]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (400, 422):
                resp.success()
            else:
                resp.failure(f"Expected 400/422, got {resp.status_code}")

    @task(1)
    def upload_empty_file(self) -> None:
        """POST /service/transcribe with empty file — expects 400/422/500."""
        with self.client.post(
            "/service/transcribe",
            files={"file": ("empty.mp3", b"", "audio/mpeg")},
            name="/service/transcribe [empty]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (400, 422):
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")
