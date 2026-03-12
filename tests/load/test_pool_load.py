"""Load tests: validates DB pool and request paths under concurrent load.

Each test spawns a headless locust process against the in-process server
started by the ``live_server_url`` fixture (see ``conftest.py``).

Run all load tests:
    uv run pytest -m load -v

Run against a real PostgreSQL instance (recommended for pool tests):
    DB_URL=postgresql://postgres:test@localhost/testdb uv run pytest -m load -v

Note: Pool exhaustion scenarios are only meaningful with PostgreSQL.
SQLite uses NullPool (no pooling), so exhaustion cannot occur.
"""

import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest

_LOCUSTFILE = Path(__file__).parent / "locustfile.py"
_RESULTS_DIR = Path(__file__).parent.parent.parent / "load_results"


def _assert_csv_p95_under(csv_path: Path, threshold_ms: int) -> None:
    """Assert the aggregated P95 response time is within ``threshold_ms``.

    Silently passes if the CSV was not written (e.g. locust exited early —
    the ``returncode`` assertion in the calling test handles that case).

    Args:
        csv_path: Path to the locust ``*_stats.csv`` file.
        threshold_ms: Maximum allowed P95 latency in milliseconds.
    """
    if not csv_path.exists():
        return
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    agg = next((r for r in rows if r["Name"] == "Aggregated"), None)
    if agg is None:
        return
    p95 = float(agg.get("95%", 0))
    assert p95 < threshold_ms, f"P95 {p95:.0f} ms exceeded threshold {threshold_ms} ms"


def _locust_cmd(
    host: str,
    users: int,
    spawn_rate: int,
    run_time: str,
    csv_name: str | None = None,
    user_classes: list[str] | None = None,
) -> list[str]:
    """Build a headless locust command list.

    Args:
        host: Base URL of the server under test.
        users: Total number of concurrent users.
        spawn_rate: Users spawned per second.
        run_time: Duration string, e.g. ``"30s"``.
        csv_name: If set, write CSV stats to ``load_results/<csv_name>``.
        user_classes: Optional list of user class names to restrict the run.

    Returns:
        list[str]: Command suitable for ``subprocess.run``.
    """
    cmd = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        str(_LOCUSTFILE),
        "--headless",
        "--users",
        str(users),
        "--spawn-rate",
        str(spawn_rate),
        "--run-time",
        run_time,
        "--host",
        host,
        "--exit-code-on-error",
        "1",
    ]
    if user_classes:
        cmd += ["--user-classes", *user_classes]
    if csv_name:
        _RESULTS_DIR.mkdir(exist_ok=True)
        cmd += ["--csv", str(_RESULTS_DIR / csv_name)]
    return cmd


@pytest.mark.load
def test_db_pool_handles_concurrent_users(live_server_url: str) -> None:
    """40 concurrent read-only users must complete with 0% failure rate.

    This is the regression test for the async SQLAlchemy migration:
    the pre-migration sync engine exhausted QueuePool at ~20 users.
    """
    result = subprocess.run(
        _locust_cmd(
            live_server_url,
            users=40,
            spawn_rate=20,
            run_time="20s",
            csv_name="pool_test",
            user_classes=["ReadOnlyUser"],
        ),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"Locust reported failures (pool exhaustion likely):\n{result.stdout}\n{result.stderr}"
    )
    _assert_csv_p95_under(_RESULTS_DIR / "pool_test_stats.csv", threshold_ms=500)


@pytest.mark.load
def test_write_path_handles_concurrent_submitters(live_server_url: str) -> None:
    """20 concurrent write users must produce 0% HTTP failures.

    Exercises the DB write path (task row creation) via LifecycleUser
    (audio upload + poll) and CombineUser (JSON-only combine + poll).
    """
    db_url = os.environ.get("DB_URL", "sqlite:///records.db")
    if db_url.startswith("sqlite"):
        pytest.skip(
            "Write-path pool contention tests are most meaningful with PostgreSQL. "
            "Set DB_URL=postgresql://... to run."
        )
    result = subprocess.run(
        _locust_cmd(
            live_server_url,
            users=20,
            spawn_rate=10,
            run_time="30s",
            csv_name="write_test",
            user_classes=["LifecycleUser", "CombineUser"],
        ),
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, (
        f"Write load test failures:\n{result.stdout}\n{result.stderr}"
    )
    _assert_csv_p95_under(_RESULTS_DIR / "write_test_stats.csv", threshold_ms=2000)


@pytest.mark.load
def test_error_paths_stable_under_load(live_server_url: str) -> None:
    """Error paths (404, 422) must remain stable at 10 concurrent error probers."""
    result = subprocess.run(
        _locust_cmd(
            live_server_url,
            users=10,
            spawn_rate=10,
            run_time="20s",
            csv_name="error_probe_test",
            user_classes=["ErrorProbeUser"],
        ),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"Error-probe load test failed:\n{result.stdout}\n{result.stderr}"
    )
    _assert_csv_p95_under(_RESULTS_DIR / "error_probe_test_stats.csv", threshold_ms=500)


@pytest.mark.load
def test_mixed_workload_db_pool_stability(live_server_url: str) -> None:
    """Realistic mixed workload (60 users, all classes) must maintain 0% failures.

    Runs all four user classes simultaneously at realistic production ratios:
    readers (6), lifecycle submitters (4), combine writers (2), error probers (1).
    """
    result = subprocess.run(
        _locust_cmd(
            live_server_url,
            users=60,
            spawn_rate=10,
            run_time="45s",
            csv_name="mixed_test",
        ),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Mixed workload test failed:\n{result.stdout}\n{result.stderr}"
    )
    _assert_csv_p95_under(_RESULTS_DIR / "mixed_test_stats.csv", threshold_ms=1000)
