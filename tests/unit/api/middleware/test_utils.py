"""Unit tests for middleware utilities."""

from unittest.mock import MagicMock

import pytest
from starlette.requests import Request

from app.api.middleware.utils import get_client_ip, sanitize_headers


def test_sanitize_headers_redacts_sensitive_headers():
    """Test that sanitize_headers redacts sensitive header values."""
    # Arrange
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer secret-token",
        "X-API-Key": "my-secret-key",
        "User-Agent": "Mozilla/5.0",
    }
    sensitive = {"authorization", "x-api-key"}

    # Act
    result = sanitize_headers(headers, sensitive)

    # Assert
    assert result["Content-Type"] == "application/json"
    assert result["Authorization"] == "***REDACTED***"
    assert result["X-API-Key"] == "***REDACTED***"
    assert result["User-Agent"] == "Mozilla/5.0"


def test_sanitize_headers_is_case_insensitive():
    """Test that header name matching is case-insensitive."""
    # Arrange
    headers = {
        "AUTHORIZATION": "Bearer token",
        "authorization": "Bearer token2",
        "Cookie": "session=abc123",
    }
    sensitive = {"authorization", "cookie"}

    # Act
    result = sanitize_headers(headers, sensitive)

    # Assert
    assert result["AUTHORIZATION"] == "***REDACTED***"
    assert result["authorization"] == "***REDACTED***"
    assert result["Cookie"] == "***REDACTED***"


def test_sanitize_headers_with_empty_sensitive_set():
    """Test that no headers are redacted when sensitive set is empty."""
    # Arrange
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer token",
    }
    sensitive = set()

    # Act
    result = sanitize_headers(headers, sensitive)

    # Assert
    assert result["Content-Type"] == "application/json"
    assert result["Authorization"] == "Bearer token"


def test_get_client_ip_from_x_forwarded_for():
    """Test extracting client IP from X-Forwarded-For header (proxy scenario)."""
    # Arrange
    request = MagicMock(spec=Request)
    request.headers = {"X-Forwarded-For": "203.0.113.1, 198.51.100.1"}
    request.client = MagicMock()
    request.client.host = "192.168.1.1"

    # Act
    result = get_client_ip(request)

    # Assert
    assert result == "203.0.113.1"  # First IP in the list


def test_get_client_ip_from_x_real_ip():
    """Test extracting client IP from X-Real-IP header (nginx scenario)."""
    # Arrange
    request = MagicMock(spec=Request)
    request.headers = {"X-Real-IP": "203.0.113.5"}
    request.client = MagicMock()
    request.client.host = "192.168.1.1"

    # Act
    result = get_client_ip(request)

    # Assert
    assert result == "203.0.113.5"


def test_get_client_ip_from_direct_connection():
    """Test extracting client IP from direct connection when no proxy headers."""
    # Arrange
    request = MagicMock(spec=Request)
    request.headers = {}
    request.client = MagicMock()
    request.client.host = "192.168.1.100"

    # Act
    result = get_client_ip(request)

    # Assert
    assert result == "192.168.1.100"


def test_get_client_ip_prioritizes_x_forwarded_for():
    """Test that X-Forwarded-For takes priority over X-Real-IP."""
    # Arrange
    request = MagicMock(spec=Request)
    request.headers = {
        "X-Forwarded-For": "203.0.113.10",
        "X-Real-IP": "203.0.113.20",
    }
    request.client = MagicMock()
    request.client.host = "192.168.1.1"

    # Act
    result = get_client_ip(request)

    # Assert
    assert result == "203.0.113.10"


def test_get_client_ip_returns_unknown_when_no_client():
    """Test that get_client_ip returns 'unknown' when no client info available."""
    # Arrange
    request = MagicMock(spec=Request)
    request.headers = {}
    request.client = None

    # Act
    result = get_client_ip(request)

    # Assert
    assert result == "unknown"


def test_get_client_ip_handles_comma_separated_list():
    """Test extracting first IP from comma-separated X-Forwarded-For list."""
    # Arrange
    request = MagicMock(spec=Request)
    request.headers = {"X-Forwarded-For": "203.0.113.1, 198.51.100.1, 192.168.1.1"}
    request.client = MagicMock()
    request.client.host = "10.0.0.1"

    # Act
    result = get_client_ip(request)

    # Assert
    assert result == "203.0.113.1"
