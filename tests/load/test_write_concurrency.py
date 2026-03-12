"""Concurrent write stress tests using httpx — no locust required.

These tests fire a precise number of simultaneous requests to exercise
race conditions and DB write contention that ramp-up locust tests may miss.

Run:
    uv run pytest tests/load/test_write_concurrency.py -m load -v
"""

import asyncio

import httpx
import pytest

from tests.load.fixtures import ALIGNED_TRANSCRIPT_BYTES, DIARIZATION_BYTES


@pytest.mark.load
def test_concurrent_writes_all_succeed(live_server_url: str) -> None:
    """30 simultaneous POST /service/combine requests must all return HTTP 200.

    Also asserts that all returned task identifiers are unique — validates
    UUID generation is correct under write contention.
    """
    n = 30

    async def submit_one(client: httpx.AsyncClient) -> dict[str, object]:
        """Submit a single combine request and return status + body."""
        resp = await client.post(
            "/service/combine",
            files={
                "aligned_transcript": (
                    "at.json",
                    ALIGNED_TRANSCRIPT_BYTES,
                    "application/json",
                ),
                "diarization_result": (
                    "dr.json",
                    DIARIZATION_BYTES,
                    "application/json",
                ),
            },
        )
        body: dict[str, object] = resp.json() if resp.status_code == 200 else {}
        return {"status": resp.status_code, "body": body}

    async def run() -> list[dict[str, object]]:
        """Fire all requests concurrently."""
        async with httpx.AsyncClient(base_url=live_server_url, timeout=30) as client:
            return list(await asyncio.gather(*[submit_one(client) for _ in range(n)]))

    results = asyncio.run(run())

    statuses = [r["status"] for r in results]
    assert all(s == 200 for s in statuses), (
        f"Some requests failed: {[s for s in statuses if s != 200]}"
    )

    identifiers = [
        body.get("identifier")
        for r in results
        if (body := r["body"]) and isinstance(body, dict)
    ]
    assert len(set(identifiers)) == n, (
        "Duplicate task IDs detected — UUID generation not unique under contention"
    )


@pytest.mark.load
def test_concurrent_reads_while_writing(live_server_url: str) -> None:
    """Simultaneous reads and writes must not produce any 5xx errors.

    15 concurrent writes (POST /service/combine) interleaved with
    15 concurrent reads (GET /task/all) in a single asyncio.gather call.
    This exercises the async DB pool's read/write interleaving at the
    exact same instant, which ramp-based locust tests cannot reproduce.
    """

    async def write(client: httpx.AsyncClient) -> int:
        """Submit a combine request and return HTTP status."""
        resp = await client.post(
            "/service/combine",
            files={
                "aligned_transcript": (
                    "at.json",
                    ALIGNED_TRANSCRIPT_BYTES,
                    "application/json",
                ),
                "diarization_result": (
                    "dr.json",
                    DIARIZATION_BYTES,
                    "application/json",
                ),
            },
        )
        return resp.status_code

    async def read(client: httpx.AsyncClient) -> int:
        """List all tasks and return HTTP status."""
        return (await client.get("/task/all")).status_code

    async def run() -> list[int]:
        """Fire 15 writes and 15 reads simultaneously."""
        async with httpx.AsyncClient(base_url=live_server_url, timeout=30) as client:
            tasks = [write(client) for _ in range(15)] + [
                read(client) for _ in range(15)
            ]
            return list(await asyncio.gather(*tasks))

    statuses = asyncio.run(run())
    errors = [s for s in statuses if s >= 500]
    assert not errors, (
        f"Got {len(errors)} 5xx responses during read/write interleaving: "
        f"{[s for s in statuses if s >= 500]}"
    )
