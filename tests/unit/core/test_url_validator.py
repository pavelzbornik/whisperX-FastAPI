"""Unit tests for URL validator SSRF protection."""

import socket
from unittest.mock import patch

import pytest

from app.core.config import SsrfSettings
from app.core.exceptions import SsrfBlockedError
from app.core.url_validator import validate_url


def _make_addrinfo(ip: str, port: int = 80) -> list[tuple]:
    """Build a fake getaddrinfo result for the given IP."""
    if ":" in ip:
        return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", (ip, port, 0, 0))]
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]


ENABLED_SETTINGS = SsrfSettings(SSRF_PROTECTION_ENABLED=True)
DISABLED_SETTINGS = SsrfSettings(SSRF_PROTECTION_ENABLED=False)


@pytest.mark.unit
class TestValidateUrlScheme:
    """Tests for URL scheme validation."""

    def test_http_allowed(self) -> None:
        """Test that http scheme is allowed."""
        with patch(
            "app.core.url_validator.socket.getaddrinfo",
            return_value=_make_addrinfo("93.184.216.34"),
        ):
            result = validate_url(
                "http://example.com/file.mp3", settings=ENABLED_SETTINGS
            )
        assert result == "http://example.com/file.mp3"

    def test_https_allowed(self) -> None:
        """Test that https scheme is allowed."""
        with patch(
            "app.core.url_validator.socket.getaddrinfo",
            return_value=_make_addrinfo("93.184.216.34"),
        ):
            result = validate_url(
                "https://example.com/file.mp3", settings=ENABLED_SETTINGS
            )
        assert result == "https://example.com/file.mp3"

    def test_file_scheme_blocked(self) -> None:
        """Test that file:// scheme is blocked."""
        with pytest.raises(SsrfBlockedError, match="Scheme 'file' is not allowed"):
            validate_url("file:///etc/passwd", settings=ENABLED_SETTINGS)

    def test_ftp_scheme_blocked(self) -> None:
        """Test that ftp:// scheme is blocked."""
        with pytest.raises(SsrfBlockedError, match="Scheme 'ftp' is not allowed"):
            validate_url("ftp://example.com/file.mp3", settings=ENABLED_SETTINGS)

    def test_gopher_scheme_blocked(self) -> None:
        """Test that gopher:// scheme is blocked."""
        with pytest.raises(SsrfBlockedError, match="Scheme 'gopher' is not allowed"):
            validate_url("gopher://example.com/", settings=ENABLED_SETTINGS)


@pytest.mark.unit
class TestValidateUrlHostname:
    """Tests for hostname validation."""

    def test_empty_hostname_blocked(self) -> None:
        """Test that URLs with no hostname are blocked."""
        with pytest.raises(SsrfBlockedError, match="no hostname"):
            validate_url("http:///path", settings=ENABLED_SETTINGS)


@pytest.mark.unit
class TestValidateUrlPrivateIp:
    """Tests for private/internal IP blocking."""

    @pytest.mark.parametrize(
        ("url", "resolved_ip", "description"),
        [
            ("http://127.0.0.1/f.mp3", "127.0.0.1", "loopback"),
            ("http://10.0.0.1/f.mp3", "10.0.0.1", "RFC1918 class A"),
            ("http://172.16.0.1/f.mp3", "172.16.0.1", "RFC1918 class B"),
            ("http://192.168.1.1/f.mp3", "192.168.1.1", "RFC1918 class C"),
            (
                "http://169.254.169.254/latest/meta-data/",
                "169.254.169.254",
                "cloud metadata",
            ),
            ("http://0.0.0.1/f.mp3", "0.0.0.1", "zero network"),
        ],
        ids=[
            "loopback",
            "rfc1918-A",
            "rfc1918-B",
            "rfc1918-C",
            "cloud-metadata",
            "zero-network",
        ],
    )
    def test_private_ip_blocked(
        self, url: str, resolved_ip: str, description: str
    ) -> None:
        """Test that private/internal IPs are blocked."""
        with patch(
            "app.core.url_validator.socket.getaddrinfo",
            return_value=_make_addrinfo(resolved_ip),
        ):
            with pytest.raises(SsrfBlockedError, match="blocked IP range"):
                validate_url(url, settings=ENABLED_SETTINGS)

    def test_ipv6_loopback_blocked(self) -> None:
        """Test that IPv6 loopback is blocked."""
        with patch(
            "app.core.url_validator.socket.getaddrinfo",
            return_value=_make_addrinfo("::1"),
        ):
            with pytest.raises(SsrfBlockedError, match="blocked IP range"):
                validate_url("http://[::1]/f.mp3", settings=ENABLED_SETTINGS)

    def test_ipv6_private_blocked(self) -> None:
        """Test that IPv6 unique local addresses are blocked."""
        with patch(
            "app.core.url_validator.socket.getaddrinfo",
            return_value=_make_addrinfo("fd00::1"),
        ):
            with pytest.raises(SsrfBlockedError, match="blocked IP range"):
                validate_url("http://[fd00::1]/f.mp3", settings=ENABLED_SETTINGS)

    def test_public_ip_allowed(self) -> None:
        """Test that public IPs are allowed."""
        with patch(
            "app.core.url_validator.socket.getaddrinfo",
            return_value=_make_addrinfo("93.184.216.34"),
        ):
            result = validate_url(
                "http://example.com/file.mp3", settings=ENABLED_SETTINGS
            )
        assert result == "http://example.com/file.mp3"


@pytest.mark.unit
class TestValidateUrlDnsResolution:
    """Tests for DNS resolution edge cases."""

    def test_dns_resolving_to_private_ip_blocked(self) -> None:
        """Test that a hostname resolving to a private IP is blocked."""
        with patch(
            "app.core.url_validator.socket.getaddrinfo",
            return_value=_make_addrinfo("127.0.0.1"),
        ):
            with pytest.raises(SsrfBlockedError, match="blocked IP range"):
                validate_url("http://evil.com/f.mp3", settings=ENABLED_SETTINGS)

    def test_dns_failure_blocked(self) -> None:
        """Test that DNS resolution failure is blocked (fail closed)."""
        with patch(
            "app.core.url_validator.socket.getaddrinfo",
            side_effect=socket.gaierror("Name resolution failed"),
        ):
            with pytest.raises(SsrfBlockedError, match="Could not resolve hostname"):
                validate_url(
                    "http://nonexistent.invalid/f.mp3", settings=ENABLED_SETTINGS
                )


@pytest.mark.unit
class TestValidateUrlConfiguration:
    """Tests for configurable SSRF settings."""

    def test_protection_disabled_allows_private_ip(self) -> None:
        """Test that disabling protection allows private IPs."""
        with patch(
            "app.core.url_validator.socket.getaddrinfo",
            return_value=_make_addrinfo("127.0.0.1"),
        ):
            result = validate_url("http://127.0.0.1/f.mp3", settings=DISABLED_SETTINGS)
        assert result == "http://127.0.0.1/f.mp3"

    def test_custom_blocked_networks(self) -> None:
        """Test that custom blocked networks are enforced."""
        custom_settings = SsrfSettings(
            SSRF_PROTECTION_ENABLED=True,
            SSRF_BLOCKED_NETWORKS=["8.8.8.0/24"],
        )
        with patch(
            "app.core.url_validator.socket.getaddrinfo",
            return_value=_make_addrinfo("8.8.8.8"),
        ):
            with pytest.raises(SsrfBlockedError, match="blocked IP range"):
                validate_url("http://dns.google/f.mp3", settings=custom_settings)

    def test_custom_allowed_schemes(self) -> None:
        """Test that custom allowed schemes are enforced."""
        https_only = SsrfSettings(
            SSRF_PROTECTION_ENABLED=True, SSRF_ALLOWED_SCHEMES=["https"]
        )
        with pytest.raises(SsrfBlockedError, match="Scheme 'http' is not allowed"):
            validate_url("http://example.com/f.mp3", settings=https_only)


@pytest.mark.unit
class TestValidateUrlExtensionBypass:
    """Tests for the extension bypass attack vector."""

    def test_metadata_with_mp3_extension_blocked(self) -> None:
        """Test that cloud metadata URL with .mp3 extension is still blocked."""
        with patch(
            "app.core.url_validator.socket.getaddrinfo",
            return_value=_make_addrinfo("169.254.169.254"),
        ):
            with pytest.raises(SsrfBlockedError, match="blocked IP range"):
                validate_url(
                    "http://169.254.169.254/latest/meta-data/iam/security-credentials/role.mp3",
                    settings=ENABLED_SETTINGS,
                )
