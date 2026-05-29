"""Unit tests for the slowapi-backed rate-limit helpers."""

import os
from collections.abc import Generator

import pytest
from starlette.requests import Request

from app.core.config import get_settings
from app.core.rate_limit import (
    rate_limit_key,
    rate_limit_value,
    rate_limiting_disabled,
    reset_rate_limiter,
)

_RL_ENV_KEYS = (
    "RATE_LIMIT__ENABLED",
    "RATE_LIMIT__REQUESTS_PER_MINUTE",
    "RATE_LIMIT__BURST",
    "RATE_LIMIT__KEY_STRATEGY",
)


@pytest.fixture
def reset_rate_limit_env() -> Generator[None, None, None]:
    """Snapshot and restore RATE_LIMIT__ env vars around each test."""
    saved = {key: os.environ.get(key) for key in _RL_ENV_KEYS}
    get_settings.cache_clear()
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


def _make_request(
    headers: dict[str, str] | None = None, client_ip: str = "1.2.3.4"
) -> Request:
    """Build a minimal Starlette Request for key-function tests."""
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/audio/transcriptions",
        "headers": raw_headers,
        "client": (client_ip, 12345),
    }
    return Request(scope)


@pytest.mark.unit
def test_key_uses_client_ip_by_default(reset_rate_limit_env: None) -> None:
    """The default ip strategy buckets by the client address."""
    os.environ["RATE_LIMIT__KEY_STRATEGY"] = "ip"
    get_settings.cache_clear()

    key = rate_limit_key(_make_request(client_ip="9.9.9.9"))

    assert key == "9.9.9.9"


@pytest.mark.unit
def test_key_uses_bearer_token_when_auth_enabled(
    reset_rate_limit_env: None,
) -> None:
    """The bearer_token strategy buckets by the validated token (auth on)."""
    os.environ["RATE_LIMIT__KEY_STRATEGY"] = "bearer_token"
    os.environ["AUTH__ENABLED"] = "true"
    os.environ["AUTH__BEARER_TOKEN"] = "s3cret"
    get_settings.cache_clear()
    try:
        key = rate_limit_key(_make_request(headers={"Authorization": "Bearer abc123"}))
        assert key == "token:abc123"
    finally:
        for k in ("AUTH__ENABLED", "AUTH__BEARER_TOKEN"):
            os.environ.pop(k, None)
        get_settings.cache_clear()


@pytest.mark.unit
def test_bearer_strategy_ignored_when_auth_disabled(
    reset_rate_limit_env: None,
) -> None:
    """Bearer-token keying is ignored without auth, falling back to IP.

    Otherwise callers could rotate arbitrary bearer values to obtain fresh
    rate-limit buckets and evade the limit entirely.
    """
    os.environ["RATE_LIMIT__KEY_STRATEGY"] = "bearer_token"
    os.environ.pop("AUTH__ENABLED", None)
    get_settings.cache_clear()

    key = rate_limit_key(
        _make_request(headers={"Authorization": "Bearer abc123"}, client_ip="7.7.7.7")
    )

    assert key == "7.7.7.7"


@pytest.mark.unit
def test_bearer_strategy_falls_back_to_ip_without_token(
    reset_rate_limit_env: None,
) -> None:
    """Without a usable token, bearer_token strategy falls back to client IP."""
    os.environ["RATE_LIMIT__KEY_STRATEGY"] = "bearer_token"
    os.environ["AUTH__ENABLED"] = "true"
    os.environ["AUTH__BEARER_TOKEN"] = "s3cret"
    get_settings.cache_clear()
    try:
        key = rate_limit_key(_make_request(client_ip="5.5.5.5"))
        assert key == "5.5.5.5"
    finally:
        for k in ("AUTH__ENABLED", "AUTH__BEARER_TOKEN"):
            os.environ.pop(k, None)
        get_settings.cache_clear()


@pytest.mark.unit
def test_rate_limit_value_reflects_settings(reset_rate_limit_env: None) -> None:
    """The limit string combines the per-minute and burst budgets."""
    os.environ["RATE_LIMIT__REQUESTS_PER_MINUTE"] = "30"
    os.environ["RATE_LIMIT__BURST"] = "3"
    get_settings.cache_clear()

    assert rate_limit_value() == "30/minute;3/second"


@pytest.mark.unit
def test_rate_limiting_disabled_reflects_settings(reset_rate_limit_env: None) -> None:
    """The exemption predicate tracks the ENABLED flag."""
    os.environ.pop("RATE_LIMIT__ENABLED", None)
    get_settings.cache_clear()
    assert rate_limiting_disabled() is True

    os.environ["RATE_LIMIT__ENABLED"] = "true"
    get_settings.cache_clear()
    assert rate_limiting_disabled() is False


@pytest.mark.unit
def test_reset_rate_limiter_is_callable() -> None:
    """The reset helper clears in-memory storage without raising."""
    reset_rate_limiter()
