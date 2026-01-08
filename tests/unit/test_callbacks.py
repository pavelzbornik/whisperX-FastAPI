"""Unit tests for callback functionality."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

import httpx
import pytest
from fastapi import HTTPException
from pydantic import HttpUrl
from pytest import MonkeyPatch

from app.callbacks import (
    post_task_callback,
    validate_callback_url,
    validate_callback_url_dependency,
)


class TestCallbacks:
    """Test callback functionality."""

    @pytest.mark.parametrize(
        "status_code,expected_result",
        [
            (200, True),  # Success
            (201, True),  # Created
            (404, False),  # Not found
            (400, False),  # Bad request
            (405, True),  # Method not allowed (explicitly allowed)
            (500, False),  # Server error
            (502, False),  # Bad gateway
        ],
    )
    def test_validate_callback_url_status_codes(
        self, status_code: int, expected_result: bool, monkeypatch: MonkeyPatch
    ) -> None:
        """Test callback URL validation with different HTTP status codes."""
        mock_response = Mock()
        mock_response.status_code = status_code

        mock_client_instance = MagicMock()
        mock_client_instance.__enter__.return_value.head.return_value = mock_response
        mock_client_instance.__exit__.return_value = None

        mock_client = Mock(return_value=mock_client_instance)

        monkeypatch.setattr("httpx.Client", mock_client)

        result = validate_callback_url("http://example.com/callback")
        assert result == expected_result

    def test_post_task_callback_success(self, monkeypatch: MonkeyPatch) -> None:
        """Test successful callback posting."""
        mock_response = Mock()
        mock_response.status_code = 200

        payload = {
            "identifier": "test-123",
            "status": "completed",
            "result": {"transcript": "test"},
        }

        mock_client_instance = MagicMock()
        mock_client_instance.__enter__.return_value.post.return_value = mock_response
        mock_client_instance.__exit__.return_value = None

        mock_client = Mock(return_value=mock_client_instance)

        monkeypatch.setattr("httpx.Client", mock_client)

        # Should not raise any exceptions
        post_task_callback("http://example.com/callback", payload)

        # Verify the POST was called with correct parameters
        mock_client_instance.__enter__.return_value.post.assert_called_once()
        call_args = mock_client_instance.__enter__.return_value.post.call_args
        assert call_args[0][0] == "http://example.com/callback"
        assert call_args[1]["json"] == payload

    def test_post_task_callback_retry_logic(self, monkeypatch: MonkeyPatch) -> None:
        """Test callback retry logic on failure."""
        payload = {"identifier": "test-123", "status": "completed"}

        mock_sleep = Mock()
        monkeypatch.setattr("time.sleep", mock_sleep)

        mock_client_instance = MagicMock()
        mock_client_instance.__exit__.return_value = None

        # First two attempts fail, third succeeds
        mock_client_instance.__enter__.return_value.post.side_effect = [
            httpx.TimeoutException("Timeout"),
            httpx.HTTPStatusError(
                "Server error",
                request=Mock(),
                response=Mock(status_code=500, text="Error"),
            ),
            Mock(status_code=200),  # Success on third attempt
        ]
        mock_client = Mock(return_value=mock_client_instance)

        monkeypatch.setattr("httpx.Client", mock_client)

        post_task_callback("http://example.com/callback", payload)

        # Should have made 3 attempts
        assert mock_client_instance.__enter__.return_value.post.call_count == 3
        # Should have slept twice (between retries)
        assert mock_sleep.call_count == 2

    def test_callback_dependency_valid_url(self, monkeypatch: MonkeyPatch) -> None:
        """Test callback URL dependency with valid URL."""
        # Override the global mock to return True for this test
        monkeypatch.setattr("app.callbacks.validate_callback_url", lambda url: True)

        result = validate_callback_url_dependency(
            HttpUrl("http://example.com/callback")
        )
        assert result == "http://example.com/callback"

    def test_callback_dependency_none_url(self) -> None:
        """Test callback URL dependency with None."""
        result = validate_callback_url_dependency(None)
        assert result is None

    def test_callback_dependency_invalid_url_raises_exception(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Test callback URL dependency with invalid URL (should raise HTTPException)."""
        monkeypatch.setattr("app.callbacks.validate_callback_url", lambda url: False)

        # Should raise HTTPException for invalid URLs
        with pytest.raises(HTTPException) as exc_info:
            validate_callback_url_dependency(HttpUrl("http://invalid.com/callback"))

        assert exc_info.value.status_code == 400
        assert "Callback URL is not reachable" in str(exc_info.value.detail)

    def test_callback_with_datetime_serialization_integration(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Integration test for callback with datetime serialization."""
        # Create payload with datetime objects
        payload = {
            "identifier": "test-123",
            "status": "completed",
            "created_at": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2023, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
            "result": {
                "processing_time": 5.2,
                "metadata": {
                    "processed_at": datetime(2023, 1, 1, 12, 5, 0, tzinfo=timezone.utc)
                },
            },
        }

        mock_response = Mock()
        mock_response.status_code = 200

        mock_client_instance = MagicMock()
        mock_client_instance.__enter__.return_value.post.return_value = mock_response
        mock_client_instance.__exit__.return_value = None

        mock_client = Mock(return_value=mock_client_instance)

        monkeypatch.setattr("httpx.Client", mock_client)

        post_task_callback("http://example.com/callback", payload)

        # Verify the payload was serialized correctly
        call_args = mock_client_instance.__enter__.return_value.post.call_args
        sent_payload = call_args[1]["json"]

        # Check that datetime objects were serialized to ISO strings
        assert sent_payload["created_at"] == "2023-01-01T12:00:00+00:00"
        assert sent_payload["updated_at"] == "2023-01-01T12:05:00+00:00"
        assert (
            sent_payload["result"]["metadata"]["processed_at"]
            == "2023-01-01T12:05:00+00:00"
        )

        assert sent_payload["identifier"] == "test-123"
        assert sent_payload["result"]["processing_time"] == 5.2
