"""Load test: validates DB pool handles 40 concurrent users without exhaustion."""

import contextlib
import subprocess
import sys
import threading
import time
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
import uvicorn


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _UvicornServer(uvicorn.Server):
    def install_signal_handlers(self) -> None:
        pass  # Required for non-main-thread use


@pytest.fixture(scope="module")
def live_server_url() -> Generator[str, None, None]:
    from app.main import app

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = _UvicornServer(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # Poll until ready
    deadline = time.time() + 10
    while time.time() < deadline:
        with contextlib.suppress(Exception):
            httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).raise_for_status()
            break
        time.sleep(0.2)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.load
def test_db_pool_handles_concurrent_users(live_server_url: str) -> None:
    """40 concurrent users must complete with 0% failure rate (validates pool fix)."""
    locustfile = Path(__file__).parent / "locustfile.py"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "locust",
            "-f",
            str(locustfile),
            "--headless",
            "--users",
            "40",
            "--spawn-rate",
            "20",
            "--run-time",
            "20s",
            "--host",
            live_server_url,
            "--exit-code-on-error",
            "1",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"Locust reported failures (pool exhaustion likely):\n{result.stdout}\n{result.stderr}"
    )
