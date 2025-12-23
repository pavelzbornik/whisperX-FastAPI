"""Unit tests for RequestIDMiddleware."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.api.middleware.request_id import RequestIDMiddleware, get_request_id
from app.core.logging_filters import request_id_var


@pytest.fixture
def middleware():
    """Create middleware instance."""
    return RequestIDMiddleware(app=MagicMock())


@pytest.fixture
def mock_request():
    """Create mock request."""
    request = MagicMock(spec=Request)
    request.headers = {}
    request.state = MagicMock()
    return request


@pytest.fixture
def mock_call_next():
    """Create mock call_next function."""
    async def call_next(request):
        response = Response()
        return response

    return call_next


@pytest.mark.asyncio
async def test_generates_request_id_when_not_provided(
    middleware, mock_request, mock_call_next
):
    """Test that middleware generates a new UUID when X-Request-ID header is not provided."""
    # Act
    response = await middleware.dispatch(mock_request, mock_call_next)

    # Assert
    assert "X-Request-ID" in response.headers
    # Verify it's a valid UUID
    request_id = response.headers["X-Request-ID"]
    assert uuid.UUID(request_id)
    assert mock_request.state.request_id == request_id


@pytest.mark.asyncio
async def test_uses_existing_request_id_from_header(
    middleware, mock_request, mock_call_next
):
    """Test that middleware uses existing X-Request-ID from client."""
    # Arrange
    existing_id = str(uuid.uuid4())
    mock_request.headers = {"X-Request-ID": existing_id}

    # Act
    response = await middleware.dispatch(mock_request, mock_call_next)

    # Assert
    assert response.headers["X-Request-ID"] == existing_id
    assert mock_request.state.request_id == existing_id


@pytest.mark.asyncio
async def test_stores_request_id_in_context_variable(
    middleware, mock_request, mock_call_next
):
    """Test that middleware stores request ID in context variable for logging."""
    # Arrange
    existing_id = str(uuid.uuid4())
    mock_request.headers = {"X-Request-ID": existing_id}

    # Act
    response = await middleware.dispatch(mock_request, mock_call_next)

    # Assert
    assert get_request_id() == existing_id


@pytest.mark.asyncio
async def test_request_id_added_to_response_headers(
    middleware, mock_request, mock_call_next
):
    """Test that request ID is always added to response headers."""
    # Act
    response = await middleware.dispatch(mock_request, mock_call_next)

    # Assert
    assert "X-Request-ID" in response.headers
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) > 0


def test_get_request_id_returns_empty_when_not_set():
    """Test that get_request_id returns empty string when context var is not set."""
    # Clear the context variable
    request_id_var.set("")

    # Act
    result = get_request_id()

    # Assert
    assert result == ""


def test_get_request_id_returns_current_id():
    """Test that get_request_id returns the current request ID from context."""
    # Arrange
    test_id = str(uuid.uuid4())
    request_id_var.set(test_id)

    # Act
    result = get_request_id()

    # Assert
    assert result == test_id

    # Cleanup
    request_id_var.set("")
