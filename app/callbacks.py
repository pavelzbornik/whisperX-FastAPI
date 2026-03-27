"""Callback functionality."""

import time
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status
from pydantic import HttpUrl

from app.core.config import get_settings
from app.core.exceptions import SsrfBlockedError
from app.core.logging import logger
from app.core.url_validator import validate_url


def _pin_url(url: str, pinned_ip: str | None) -> tuple[str, dict[str, str]]:
    """Replace hostname with pinned IP in URL, returning Host header.

    Args:
        url: Original URL.
        pinned_ip: Validated IP to pin, or None to skip pinning.

    Returns:
        Tuple of (pinned_url, extra_headers).
    """
    if not pinned_ip:
        return url, {}

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return url, {}

    ip_host = f"[{pinned_ip}]" if ":" in pinned_ip else pinned_ip
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    pinned = url.replace(
        f"{parsed.scheme}://{parsed.netloc}",
        f"{parsed.scheme}://{ip_host}:{port}",
    )
    port_suffix = f":{parsed.port}" if parsed.port else ""
    return pinned, {"Host": f"{hostname}{port_suffix}"}


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
        pinned_url, headers = _pin_url(callback_url, pinned_ip)
        with httpx.Client(
            timeout=float(get_settings().callback.CALLBACK_TIMEOUT),
            headers=headers,
        ) as client:
            response = client.head(pinned_url)
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
    pinned_url, pin_headers = _pin_url(callback_url, pinned_ip)

    for attempt in range(max_retries):
        try:
            with httpx.Client(
                timeout=float(get_settings().callback.CALLBACK_TIMEOUT),
                headers=pin_headers,
            ) as client:
                response = client.post(pinned_url, json=serialized_payload)
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
