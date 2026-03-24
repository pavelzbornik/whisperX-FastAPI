"""URL validation for SSRF protection.

Validates URLs before outbound HTTP requests to prevent Server-Side
Request Forgery attacks. Checks URL scheme, resolves the hostname,
and verifies the resolved IP is not in a blocked network range.
"""

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import SsrfSettings, get_settings
from app.core.exceptions import SsrfBlockedError


def validate_url(url: str, settings: SsrfSettings | None = None) -> str:
    """Validate a URL against SSRF rules.

    Args:
        url: The URL to validate.
        settings: SSRF settings override. If None, loaded from get_settings().

    Returns:
        The validated URL (unchanged).

    Raises:
        SsrfBlockedError: If the URL is blocked by SSRF rules.
    """
    if settings is None:
        settings = get_settings().ssrf

    if not settings.SSRF_PROTECTION_ENABLED:
        return url

    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in settings.SSRF_ALLOWED_SCHEMES:
        raise SsrfBlockedError(
            url=url,
            reason=f"Scheme '{parsed.scheme}' is not allowed. "
            f"Allowed: {', '.join(settings.SSRF_ALLOWED_SCHEMES)}",
        )

    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        raise SsrfBlockedError(url=url, reason="URL has no hostname")

    # Resolve hostname and check all IPs against blocked networks
    try:
        addrinfo = socket.getaddrinfo(hostname, parsed.port or 80)
    except socket.gaierror:
        raise SsrfBlockedError(
            url=url, reason=f"Could not resolve hostname '{hostname}'"
        )

    blocked_networks = [
        ipaddress.ip_network(cidr, strict=False)
        for cidr in settings.SSRF_BLOCKED_NETWORKS
    ]

    for family, _type, _proto, _canonname, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        for network in blocked_networks:
            if ip in network:
                raise SsrfBlockedError(
                    url=url,
                    reason=f"URL resolves to blocked IP range ({ip} in {network})",
                )

    return url
