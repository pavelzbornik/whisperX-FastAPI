"""Unit tests for ErrorHandlingMiddleware."""

from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.middleware.error_handling import ErrorHandlingMiddleware


@pytest.fixture
def middleware():
    """Create middleware instance."""
    return ErrorHandlingMiddleware(app=MagicMock())


@pytest.fixture
def mock_request():
    """Create mock request."""
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url = MagicMock()
    request.url.path = "/test"
    return request


@pytest.mark.asyncio
async def test_returns_response_on_success(middleware, mock_request):
    """Test that middleware returns normal response when no exception occurs."""

    async def successful_call_next(request):
        return JSONResponse(content={"status": "ok"})

    # Act
    with patch("app.api.middleware.error_handling.get_request_id") as mock_get_id:
        mock_get_id.return_value = "test-request-id"
        response = await middleware.dispatch(mock_request, successful_call_next)

    # Assert
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_catches_and_handles_exceptions(middleware, mock_request):
    """Test that middleware catches exceptions and returns error response."""

    async def failing_call_next(request):
        raise ValueError("Test error")

    # Act
    with (
        patch("app.api.middleware.error_handling.get_request_id") as mock_get_id,
        patch("app.api.middleware.error_handling.get_settings") as mock_settings,
    ):
        mock_get_id.return_value = "test-request-id"
        mock_settings.return_value.ENVIRONMENT = "production"

        response = await middleware.dispatch(mock_request, failing_call_next)

    # Assert
    assert isinstance(response, JSONResponse)
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_includes_request_id_in_error_response(middleware, mock_request):
    """Test that error response includes the correlation ID."""

    async def failing_call_next(request):
        raise RuntimeError("Test error")

    # Act
    with (
        patch("app.api.middleware.error_handling.get_request_id") as mock_get_id,
        patch("app.api.middleware.error_handling.get_settings") as mock_settings,
    ):
        mock_get_id.return_value = "test-correlation-id"
        mock_settings.return_value.ENVIRONMENT = "production"

        response = await middleware.dispatch(mock_request, failing_call_next)

    # Assert
    import json

    response_data = json.loads(response.body.decode())
    assert response_data["request_id"] == "test-correlation-id"


@pytest.mark.asyncio
async def test_hides_error_details_in_production(middleware, mock_request):
    """Test that error details are hidden in production environment."""

    async def failing_call_next(request):
        raise ValueError("Sensitive error message")

    # Act
    with (
        patch("app.api.middleware.error_handling.get_request_id") as mock_get_id,
        patch("app.api.middleware.error_handling.get_settings") as mock_settings,
    ):
        mock_get_id.return_value = "test-request-id"
        mock_settings.return_value.ENVIRONMENT = "production"

        response = await middleware.dispatch(mock_request, failing_call_next)

    # Assert
    import json

    response_data = json.loads(response.body.decode())
    assert response_data["message"] == "Internal server error"
    assert "error" not in response_data  # Details not exposed
    assert "type" not in response_data


@pytest.mark.asyncio
async def test_shows_error_details_in_development(middleware, mock_request):
    """Test that error details are shown in development environment."""

    async def failing_call_next(request):
        raise ValueError("Test error message")

    # Act
    with (
        patch("app.api.middleware.error_handling.get_request_id") as mock_get_id,
        patch("app.api.middleware.error_handling.get_settings") as mock_settings,
    ):
        mock_get_id.return_value = "test-request-id"
        mock_settings.return_value.ENVIRONMENT = "development"

        response = await middleware.dispatch(mock_request, failing_call_next)

    # Assert
    import json

    response_data = json.loads(response.body.decode())
    assert "error" in response_data
    assert response_data["error"] == "Test error message"
    assert "type" in response_data
    assert response_data["type"] == "ValueError"


@pytest.mark.asyncio
async def test_logs_exception_with_correlation_id(middleware, mock_request):
    """Test that exceptions are logged with correlation ID."""

    async def failing_call_next(request):
        raise RuntimeError("Test exception")

    # Act
    with (
        patch("app.api.middleware.error_handling.get_request_id") as mock_get_id,
        patch("app.api.middleware.error_handling.get_settings") as mock_settings,
        patch("app.api.middleware.error_handling.logger") as mock_logger,
    ):
        mock_get_id.return_value = "correlation-123"
        mock_settings.return_value.ENVIRONMENT = "production"

        await middleware.dispatch(mock_request, failing_call_next)

        # Assert
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "RuntimeError" in call_args[0][0]
        assert call_args[1]["extra"]["request_id"] == "correlation-123"
