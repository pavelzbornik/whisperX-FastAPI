"""Unit tests for RequestLoggingMiddleware."""

from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.api.middleware.request_logging import RequestLoggingMiddleware


@pytest.fixture
def middleware():
    """Create middleware instance."""
    return RequestLoggingMiddleware(app=MagicMock())


@pytest.fixture
def mock_request():
    """Create mock request."""
    request = MagicMock(spec=Request)
    request.method = "POST"
    request.url = MagicMock()
    request.url.path = "/api/test"
    request.query_params = {}
    request.headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer secret-token",
        "X-API-Key": "secret-key",
    }
    request.client = MagicMock()
    request.client.host = "192.168.1.1"
    return request


@pytest.fixture
def mock_call_next():
    """Create mock call_next function."""

    async def call_next(request):
        response = Response()
        response.status_code = 200
        return response

    return call_next


@pytest.mark.asyncio
async def test_logs_request_start(middleware, mock_request, mock_call_next):
    """Test that middleware logs request start with details."""
    with (
        patch("app.api.middleware.request_logging.get_settings") as mock_settings,
        patch("app.api.middleware.request_logging.logger") as mock_logger,
    ):
        mock_settings.return_value.middleware.ENABLE_REQUEST_LOGGING = True
        mock_settings.return_value.middleware.SENSITIVE_HEADERS = {
            "authorization",
            "x-api-key",
        }

        # Act
        await middleware.dispatch(mock_request, mock_call_next)

        # Assert - check first info call (request start)
        assert mock_logger.info.call_count >= 2
        first_call = mock_logger.info.call_args_list[0]
        assert "Request started: POST /api/test" in first_call[0][0]


@pytest.mark.asyncio
async def test_sanitizes_sensitive_headers(middleware, mock_request, mock_call_next):
    """Test that middleware sanitizes sensitive headers in logs."""
    with (
        patch("app.api.middleware.request_logging.get_settings") as mock_settings,
        patch("app.api.middleware.request_logging.logger") as mock_logger,
    ):
        mock_settings.return_value.middleware.ENABLE_REQUEST_LOGGING = True
        mock_settings.return_value.middleware.SENSITIVE_HEADERS = {
            "authorization",
            "x-api-key",
        }

        # Act
        await middleware.dispatch(mock_request, mock_call_next)

        # Assert
        first_call = mock_logger.info.call_args_list[0]
        extra_data = first_call[1]["extra"]

        # Check headers are sanitized
        assert "***REDACTED***" in str(extra_data["headers"].get("authorization", ""))
        assert "***REDACTED***" in str(extra_data["headers"].get("x-api-key", ""))
        assert "application/json" in str(extra_data["headers"].get("content-type", ""))


@pytest.mark.asyncio
async def test_logs_response_completion(middleware, mock_request, mock_call_next):
    """Test that middleware logs response completion with status code."""
    with (
        patch("app.api.middleware.request_logging.get_settings") as mock_settings,
        patch("app.api.middleware.request_logging.logger") as mock_logger,
    ):
        mock_settings.return_value.middleware.ENABLE_REQUEST_LOGGING = True
        mock_settings.return_value.middleware.SENSITIVE_HEADERS = set()

        # Act
        await middleware.dispatch(mock_request, mock_call_next)

        # Assert - check second info call (response completion)
        assert mock_logger.info.call_count >= 2
        second_call = mock_logger.info.call_args_list[1]
        assert "Request completed: POST /api/test" in second_call[0][0]
        assert "(status: 200)" in second_call[0][0]


@pytest.mark.asyncio
async def test_logs_errors_on_exception(middleware, mock_request):
    """Test that middleware logs errors when exceptions occur."""

    # Mock call_next that raises exception
    async def failing_call_next(request):
        raise ValueError("Test error")

    with (
        patch("app.api.middleware.request_logging.get_settings") as mock_settings,
        patch("app.api.middleware.request_logging.logger") as mock_logger,
    ):
        mock_settings.return_value.middleware.ENABLE_REQUEST_LOGGING = True
        mock_settings.return_value.middleware.SENSITIVE_HEADERS = set()

        # Act & Assert
        with pytest.raises(ValueError):
            await middleware.dispatch(mock_request, failing_call_next)

        # Check error was logged
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "Request failed: POST /api/test" in call_args


@pytest.mark.asyncio
async def test_skips_logging_when_disabled(middleware, mock_request, mock_call_next):
    """Test that middleware skips logging when ENABLE_REQUEST_LOGGING is False."""
    with (
        patch("app.api.middleware.request_logging.get_settings") as mock_settings,
        patch("app.api.middleware.request_logging.logger") as mock_logger,
    ):
        mock_settings.return_value.middleware.ENABLE_REQUEST_LOGGING = False

        # Act
        await middleware.dispatch(mock_request, mock_call_next)

        # Assert - no logging should occur
        mock_logger.info.assert_not_called()
        mock_logger.error.assert_not_called()
