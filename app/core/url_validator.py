"""URL validation for SSRF protection.

Validates URLs before outbound HTTP requests to prevent Server-Side
Request Forgery attacks. Checks URL scheme, resolves the hostname,
and verifies the resolved IP is not in a blocked network range.

Returns a validated IP to pin into the HTTP request, preventing
DNS rebinding (TOCTOU) attacks.
"""

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import SsrfSettings, get_settings
from app.core.exceptions import SsrfBlockedError
from app.core.logging import logger


def _check_ip_blocked(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    blocked_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> ipaddress.IPv4Network | ipaddress.IPv6Network | None:
    """Check if an IP falls in any blocked network, handling IPv4-mapped IPv6.

    Returns the matching network if blocked, None otherwise.
    """
    # Check the IP directly
    for network in blocked_networks:
        if ip in network:
            return network

    # Handle IPv4-mapped IPv6 (e.g., ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        for network in blocked_networks:
            if ip.ipv4_mapped in network:
                return network

    return None


def validate_url(
    url: str, settings: SsrfSettings | None = None
) -> tuple[str, str | None]:
    """Validate a URL against SSRF rules and return a pinned IP.

    Resolves the hostname once and returns the validated IP so callers
    can pin the connection to that IP, preventing DNS rebinding attacks.

    Args:
        url: The URL to validate.
        settings: SSRF settings override. If None, loaded from get_settings().

    Returns:
        Tuple of (validated_url, pinned_ip). pinned_ip is None when
        SSRF protection is disabled.

    Raises:
        SsrfBlockedError: If the URL is blocked by SSRF rules.
    """
    if settings is None:
        settings = get_settings().ssrf

    if not settings.SSRF_PROTECTION_ENABLED:
        return url, None

    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in settings.SSRF_ALLOWED_SCHEMES:
        logger.warning(
            "SSRF blocked: scheme '%s' not allowed for URL: %s",
            parsed.scheme,
            url,
        )
        raise SsrfBlockedError(
            url=url,
            reason=f"Scheme '{parsed.scheme}' is not allowed. "
            f"Allowed: {', '.join(settings.SSRF_ALLOWED_SCHEMES)}",
        )

    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        logger.warning("SSRF blocked: URL has no hostname: %s", url)
        raise SsrfBlockedError(url=url, reason="URL has no hostname")

    # Resolve hostname and check all IPs against blocked networks
    try:
        addrinfo = socket.getaddrinfo(hostname, parsed.port or 80)
    except socket.gaierror:
        logger.warning(
            "SSRF blocked: could not resolve hostname '%s' for URL: %s",
            hostname,
            url,
        )
        raise SsrfBlockedError(
            url=url, reason=f"Could not resolve hostname '{hostname}'"
        ) from None

    blocked_networks = [
        ipaddress.ip_network(cidr, strict=False)
        for cidr in settings.SSRF_BLOCKED_NETWORKS
    ]

    validated_ip: str | None = None

    for _family, _type, _proto, _canonname, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        matched_network = _check_ip_blocked(ip, blocked_networks)
        if matched_network:
            logger.warning(
                "SSRF blocked: URL '%s' resolves to %s (blocked by %s)",
                url,
                ip,
                matched_network,
            )
            raise SsrfBlockedError(
                url=url,
                reason=f"URL resolves to blocked IP range ({ip} in {matched_network})",
            )

        # Use the first validated IP for pinning
        if validated_ip is None:
            validated_ip = str(ip)

    return url, validated_ip
