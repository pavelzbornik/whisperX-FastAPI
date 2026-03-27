"""Callback functionality."""

import contextlib
import socket
import threading
import time
from collections.abc import Generator
from datetime import datetime
from typing import Any

import httpx
from fastapi import HTTPException, status
from pydantic import HttpUrl

from app.core.config import get_settings
from app.core.exceptions import SsrfBlockedError
from app.core.logging import logger
from app.core.url_validator import validate_url

# Thread-local storage for DNS pinning in httpx callbacks.
_dns_pin_local = threading.local()
_original_getaddrinfo = socket.getaddrinfo


def _thread_aware_getaddrinfo(host: object, *args: object, **kwargs: object) -> object:
    """Thread-aware getaddrinfo that uses pinned IP if set for this thread."""
    pinned_ip = getattr(_dns_pin_local, "pinned_ip", None)
    if pinned_ip:
        host = pinned_ip
    return _original_getaddrinfo(host, *args, **kwargs)  # type: ignore[arg-type]


# Install once at import time — thread-safe via thread-local check.
socket.getaddrinfo = _thread_aware_getaddrinfo  # type: ignore[assignment]


@contextlib.contextmanager
def _pinned_dns(pinned_ip: str | None) -> Generator[None, None, None]:
    """Context manager that pins DNS resolution to a validated IP.

    Sets a thread-local pinned IP so that the thread-aware getaddrinfo
    wrapper returns the pinned IP for any hostname lookup. Other threads
    are not affected. The original hostname is preserved in the URL for
    correct TLS SNI and certificate verification.

    Args:
        pinned_ip: IP to pin, or None to skip pinning.
    """
    if not pinned_ip:
        yield
        return

    _dns_pin_local.pinned_ip = pinned_ip
    try:
        yield
    finally:
        _dns_pin_local.pinned_ip = None


def validate_callback_url(callback_url: str) -> bool:
    """
    Validate that a callback URL is reachable.

    Args:
        callback_url: The callback URL to validate

    Returns:
        bool: True if the URL is reachable, False otherwise

    Raises:
        SsrfBlockedError: If the URL is blocked by SSRF protection
    """
    # Let SSRF errors propagate — they should not be silently swallowed
    _, pinned_ip = validate_url(callback_url)

    try:
        with (
            _pinned_dns(pinned_ip),
            httpx.Client(
                timeout=float(get_settings().callback.CALLBACK_TIMEOUT),
            ) as client,
        ):
            response = client.head(callback_url)
            if response.status_code < 400 or response.status_code == 405:
                return True
            else:
                logger.warning(
                    "Callback URL returned server error %d: %s",
                    response.status_code,
                    callback_url,
                )
                return False
    except httpx.ConnectError:
        logger.warning(
            "Callback URL not reachable (connection error): %s", callback_url
        )
        return False
    except httpx.TimeoutException:
        logger.warning("Callback URL validation timeout: %s", callback_url)
        return False
    except Exception as e:
        logger.warning("Callback URL validation failed: %s - %s", callback_url, str(e))
        return False


def validate_callback_url_dependency(
    callback_url: HttpUrl | None = None,
) -> str | None:
    """
    Fastapi dependency to validate callback URL during request validation.

    Args:
        callback_url: Optional callback URL from request

    Returns:
        str | None: Validated callback URL as string, or None if not provided

    Raises:
        HTTPException: If callback URL validation fails
    """
    if callback_url is None:
        return None

    callback_url_str = str(callback_url)

    try:
        if not validate_callback_url(callback_url_str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Callback URL is not reachable: {callback_url_str}",
            )
    except SsrfBlockedError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The provided callback URL is not allowed.",
        ) from None

    return callback_url_str


def _serialize_datetime(obj: Any) -> Any:
    """Recursively serialize datetime objects to ISO format strings."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: _serialize_datetime(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_datetime(item) for item in obj]
    else:
        return obj


def post_task_callback(callback_url: str, payload: dict[str, Any]) -> None:
    """
    POST task callback with serialized datetime objects and retry logic.

    Args:
        callback_url: The URL to send the callback to
        payload: The payload to send
    """
    max_retries = get_settings().callback.CALLBACK_MAX_RETRIES

    serialized_payload = _serialize_datetime(payload)

    # Validate URL before sending callback (defense in depth — DNS could change)
    _, pinned_ip = validate_url(callback_url)

    for attempt in range(max_retries):
        try:
            with (
                _pinned_dns(pinned_ip),
                httpx.Client(
                    timeout=float(get_settings().callback.CALLBACK_TIMEOUT),
                ) as client,
            ):
                response = client.post(callback_url, json=serialized_payload)
                response.raise_for_status()

            logger.info(
                "Successfully posted callback to %s",
                callback_url,
            )
            return

        except httpx.TimeoutException as e:
            logger.warning(
                "Timeout posting callback to %s (attempt %d/%d): %s",
                callback_url,
                attempt + 1,
                max_retries,
                str(e),
            )
        except httpx.HTTPStatusError as e:
            logger.warning(
                "HTTP error posting callback to %s (attempt %d/%d): %s - %s",
                callback_url,
                attempt + 1,
                max_retries,
                e.response.status_code,
                e.response.text[:200],
            )
        except Exception as e:
            logger.warning(
                "Failed to POST callback to %s (attempt %d/%d): %s",
                callback_url,
                attempt + 1,
                max_retries,
                str(e),
            )

        if attempt < max_retries - 1:
            wait_time = 2**attempt
            logger.debug("Waiting %ss before retry...", wait_time)
            time.sleep(wait_time)

    logger.error(
        "All callback attempts failed for %s, after %d attempts",
        callback_url,
        max_retries,
    )
