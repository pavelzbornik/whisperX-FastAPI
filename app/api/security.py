"""FastAPI security dependencies: bearer-token auth and concurrency gates.

Configuration is read from :func:`app.core.config.get_settings`, which is loaded
once from the environment/``.env`` at startup (it is ``lru_cache``-backed). The
relevant features stay off (no-op) until explicitly enabled; changing the values
requires a process restart. Tests clear the relevant caches to re-read them.
"""

import hmac
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Header

from app.core.concurrency import (
    get_async_concurrency_gate,
    get_sync_concurrency_gate,
)
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ServiceOverloadedError


def verify_bearer_token(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> None:
    """Validate the shared bearer token when authentication is enabled.

    A no-op when ``AUTH__ENABLED`` is false (the default), preserving the prior
    unauthenticated behavior. When enabled, a missing or non-matching token is
    rejected with :class:`AuthenticationError` (HTTP 401). The comparison is
    constant-time to avoid leaking the token via timing.

    Args:
        authorization: The raw ``Authorization`` request header, if present.

    Raises:
        AuthenticationError: If auth is enabled and the token is absent/invalid.
    """
    settings = get_settings()
    if not settings.auth.ENABLED:
        return

    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError(reason="Missing bearer token")

    presented = authorization[len("bearer ") :].strip()
    if not presented or not hmac.compare_digest(presented, settings.auth.BEARER_TOKEN):
        raise AuthenticationError(reason="Invalid bearer token")


async def enforce_sync_gpu_quota() -> AsyncGenerator[None, None]:
    """Hold a slot on the synchronous-path concurrency gate for the request.

    Rejects with :class:`ServiceOverloadedError` (HTTP 503) when the sync budget
    is exhausted instead of stalling the connection. The slot is released when
    the request finishes. A no-op when ``MAX_QUEUED_GPU_REQUESTS`` is 0.

    Yields:
        None — control returns to the request handler while the slot is held.

    Raises:
        ServiceOverloadedError: If no sync slot is currently available.
    """
    gate = get_sync_concurrency_gate()
    if not gate.acquire():
        raise ServiceOverloadedError(scope="sync")
    try:
        yield
    finally:
        gate.release()


async def enforce_async_gpu_quota() -> AsyncGenerator[None, None]:
    """Hold a slot on the asynchronous-path concurrency gate for the request.

    Admission control for the async endpoints: the slot is held only for the
    request phase (file validation, audio decode, task enqueue) and released
    when the HTTP response is sent. The GPU pipeline itself runs later in a
    background task and is bounded by the GPU semaphore
    (``MAX_CONCURRENT_GPU_TASKS``), not by this gate — so this caps how many
    async requests are admitted concurrently, not the queued background backlog.

    Rejects with :class:`ServiceOverloadedError` (HTTP 503) when the async
    budget is exhausted. A no-op when ``MAX_QUEUED_GPU_REQUESTS`` is 0.

    Yields:
        None — control returns to the request handler while the slot is held.

    Raises:
        ServiceOverloadedError: If no async slot is currently available.
    """
    gate = get_async_concurrency_gate()
    if not gate.acquire():
        raise ServiceOverloadedError(scope="async")
    try:
        yield
    finally:
        gate.release()
