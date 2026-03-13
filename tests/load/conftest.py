"""Shared fixtures for load tests."""

import contextlib
import threading
import time
from collections.abc import Generator

import httpx
import pytest
import uvicorn


def _free_port() -> int:
    """Return a free TCP port on localhost."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class _UvicornServer(uvicorn.Server):
    """Uvicorn server that can run outside the main thread."""

    def install_signal_handlers(self) -> None:
        """Skip signal handler installation for non-main-thread use."""


@pytest.fixture(scope="module")
def live_server_url() -> Generator[str, None, None]:
    """Start a live uvicorn server and yield its base URL.

    The server runs the production app container. ML background tasks will
    fail immediately (no models loaded), which is acceptable — load tests
    target the HTTP + DB layer, not ML correctness.

    Yields:
        str: Base URL of the running server, e.g. ``http://127.0.0.1:54321``.
    """
    from app.main import app

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = _UvicornServer(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while time.time() < deadline:
        with contextlib.suppress(Exception):
            httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).raise_for_status()
            break
        time.sleep(0.2)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)
