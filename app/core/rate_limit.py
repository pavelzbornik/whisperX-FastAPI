"""Per-caller rate limiting backed by slowapi.

The :data:`limiter` is constructed once at import time, but its behaviour is
driven by :func:`app.core.config.get_settings` on *every* request via the
dynamic limit string, the key function, and the exemption predicate. Because
``get_settings`` is ``lru_cache``-backed (loaded from the environment/``.env``
at startup), the effective values are fixed for the life of the process; the
per-request reads exist so the limit/strategy/enabled flag are evaluated
together and so tests can clear the cache to re-read updated settings.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import RateLimitKeyStrategy, get_settings


def rate_limit_key(request: Request) -> str:
    """Return the rate-limit bucket key for the current request.

    Honors ``RATE_LIMIT__KEY_STRATEGY``. ``bearer_token`` is only used when
    ``AUTH__ENABLED`` is true — by then the auth dependency has already
    rejected requests with missing or invalid tokens, so the bucket key
    refers to a token the server has validated. When auth is disabled the
    strategy falls back to the client IP, otherwise callers could rotate
    arbitrary bearer values to obtain fresh rate-limit buckets and evade
    the limit. ``ip`` (the default) always buckets by client IP.

    Args:
        request: The incoming request.

    Returns:
        A string key identifying the caller for rate-limit accounting.
    """
    settings = get_settings()
    if (
        settings.rate_limit.KEY_STRATEGY == RateLimitKeyStrategy.bearer_token
        and settings.auth.ENABLED
    ):
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
            if token:
                return f"token:{token}"
    return str(get_remote_address(request))


def rate_limit_value() -> str:
    """Return the slowapi limit string derived from current settings.

    Combines the sustained per-minute budget with a short-term per-second burst
    budget, e.g. ``"60/minute;10/second"``. Evaluated per request so config
    changes take effect immediately.
    """
    rl = get_settings().rate_limit
    return f"{rl.REQUESTS_PER_MINUTE}/minute;{rl.BURST}/second"


def rate_limiting_disabled() -> bool:
    """Return ``True`` when rate limiting is disabled.

    Used as the slowapi ``exempt_when`` predicate so that, when disabled, the
    limit is skipped entirely and no rate-limit headers are emitted.
    """
    return not get_settings().rate_limit.ENABLED


limiter = Limiter(
    key_func=rate_limit_key,
    headers_enabled=True,
    enabled=True,
)


def reset_rate_limiter() -> None:
    """Clear the limiter's in-memory storage.

    Intended for test isolation so accumulated request counts do not leak
    between tests sharing the same process.
    """
    limiter.reset()
