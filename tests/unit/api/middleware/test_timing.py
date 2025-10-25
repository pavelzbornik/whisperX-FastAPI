"""Unit tests for TimingMiddleware."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.api.middleware.timing import TimingMiddleware


@pytest.fixture
def middleware():
    """Create middleware instance."""
    return TimingMiddleware(app=MagicMock())


@pytest.fixture
def mock_request():
    """Create mock request."""
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url = MagicMock()
    request.url.path = "/test"
    return request


@pytest.fixture
def mock_call_next():
    """Create mock call_next function."""

    async def call_next(request):
        # Simulate some processing time
        await asyncio.sleep(0.01)
        response = Response()
        response.status_code = 200
        return response

    return call_next


@pytest.mark.asyncio
async def test_adds_response_time_header(middleware, mock_request, mock_call_next):
    """Test that middleware adds X-Response-Time header to response."""
    # Act
    response = await middleware.dispatch(mock_request, mock_call_next)

    # Assert
    assert "X-Response-Time" in response.headers
    response_time = response.headers["X-Response-Time"]
    assert response_time.endswith("ms")


@pytest.mark.asyncio
async def test_logs_request_completion(middleware, mock_request, mock_call_next):
    """Test that middleware logs request completion with timing."""
    # Act
    with patch("app.api.middleware.timing.logger") as mock_logger:
        response = await middleware.dispatch(mock_request, mock_call_next)

        # Assert
        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args[0][0]
        assert "GET /test completed in" in call_args
        assert "ms" in call_args


@pytest.mark.asyncio
async def test_logs_slow_requests(middleware, mock_request):
    """Test that middleware logs warning for slow requests."""

    # Mock slow call_next
    async def slow_call_next(request):
        await asyncio.sleep(0.1)  # Simulate slow request
        response = Response()
        response.status_code = 200
        return response

    # Mock settings to have low threshold
    with (
        patch("app.api.middleware.timing.get_settings") as mock_settings,
        patch("app.api.middleware.timing.logger") as mock_logger,
    ):
        mock_settings.return_value.middleware.SLOW_REQUEST_THRESHOLD = 0.05

        # Act
        response = await middleware.dispatch(mock_request, slow_call_next)

        # Assert
        mock_logger.warning.assert_called()
        call_args = mock_logger.warning.call_args[0][0]
        assert "Slow request detected" in call_args


@pytest.mark.asyncio
async def test_timing_accuracy(middleware, mock_request):
    """Test that timing measurement is reasonably accurate."""

    # Create call_next with known delay
    async def timed_call_next(request):
        await asyncio.sleep(0.05)  # 50ms delay
        response = Response()
        response.status_code = 200
        return response

    # Act
    response = await middleware.dispatch(mock_request, timed_call_next)

    # Assert
    response_time_str = response.headers["X-Response-Time"]
    response_time_ms = float(response_time_str.replace("ms", ""))

    # Should be approximately 50ms (allow for some variance)
    assert 40 <= response_time_ms <= 70


# Need to import asyncio for the tests
import asyncio
