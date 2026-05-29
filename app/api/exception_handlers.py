"""Exception handlers for FastAPI application.

This module defines handlers that map domain exceptions to HTTP responses,
ensuring consistent error formatting and proper separation of concerns.
"""

import logging
import uuid

from fastapi import Request, status
from fastapi.responses import JSONResponse, Response
from slowapi.errors import RateLimitExceeded

from app.core.exceptions import (
    AuthenticationError,
    DomainError,
    InfrastructureError,
    ServiceOverloadedError,
    SpeakerNotFoundError,
    TaskNotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)


def domain_error_handler(
    request: Request, exc: DomainError | Exception
) -> JSONResponse:
    """Handle domain errors (business logic violations).

    Domain errors typically indicate that a business rule was violated or
    a domain operation cannot be completed. These map to HTTP 400 Bad Request.

    Args:
        request: FastAPI request object
        exc: Domain error exception

    Returns:
        JSONResponse with error details and HTTP 400 status
    """
    # Cast to DomainError since we know it will be that type
    domain_exc = exc if isinstance(exc, DomainError) else DomainError(str(exc))

    logger.warning(
        "Domain error: %s",
        domain_exc.message,
        extra={
            "correlation_id": domain_exc.correlation_id,
            "code": domain_exc.code,
            "path": request.url.path,
        },
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, content=domain_exc.to_dict()
    )


def validation_error_handler(
    request: Request, exc: ValidationError | Exception
) -> JSONResponse:
    """Handle validation errors.

    Validation errors indicate that user input failed validation rules.
    These map to HTTP 422 Unprocessable Entity.

    Args:
        request: FastAPI request object
        exc: Validation error exception

    Returns:
        JSONResponse with error details and HTTP 422 status
    """
    # Cast to ValidationError since we know it will be that type
    val_exc = exc if isinstance(exc, ValidationError) else ValidationError(str(exc))

    logger.info(
        "Validation error: %s",
        val_exc.message,
        extra={"correlation_id": val_exc.correlation_id, "path": request.url.path},
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=val_exc.to_dict()
    )


def task_not_found_handler(
    request: Request, exc: TaskNotFoundError | Exception
) -> JSONResponse:
    """Handle task not found errors.

    Task not found errors indicate that a requested task doesn't exist.
    These map to HTTP 404 Not Found.

    Args:
        request: FastAPI request object
        exc: Task not found error exception

    Returns:
        JSONResponse with error details and HTTP 404 status
    """
    # Cast to TaskNotFoundError since we know it will be that type
    task_exc = (
        exc if isinstance(exc, TaskNotFoundError) else TaskNotFoundError("unknown")
    )

    logger.info(
        "Task not found: %s",
        task_exc.details.get("identifier"),
        extra={"correlation_id": task_exc.correlation_id, "path": request.url.path},
    )

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content=task_exc.to_dict()
    )


def speaker_not_found_handler(
    request: Request, exc: SpeakerNotFoundError | Exception
) -> JSONResponse:
    """Handle speaker not found errors.

    Args:
        request: FastAPI request object
        exc: Speaker not found error exception

    Returns:
        JSONResponse with error details and HTTP 404 status
    """
    speaker_exc = (
        exc
        if isinstance(exc, SpeakerNotFoundError)
        else SpeakerNotFoundError("unknown")
    )

    logger.info(
        "Speaker not found: %s",
        speaker_exc.details.get("identifier"),
        extra={"correlation_id": speaker_exc.correlation_id, "path": request.url.path},
    )

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content=speaker_exc.to_dict()
    )


def infrastructure_error_handler(
    request: Request, exc: InfrastructureError | Exception
) -> JSONResponse:
    """Handle infrastructure errors (external system failures).

    Infrastructure errors indicate that an external dependency has failed.
    These map to HTTP 503 Service Unavailable. Internal details are hidden
    from users for security, but logged for debugging.

    Args:
        request: FastAPI request object
        exc: Infrastructure error exception

    Returns:
        JSONResponse with error details and HTTP 503 status
    """
    # Cast to InfrastructureError since we know it will be that type
    infra_exc = (
        exc if isinstance(exc, InfrastructureError) else InfrastructureError(str(exc))
    )

    logger.error(
        "Infrastructure error: %s",
        infra_exc.message,
        extra={
            "correlation_id": infra_exc.correlation_id,
            "code": infra_exc.code,
            "path": request.url.path,
        },
        exc_info=True,
    )

    # Don't expose internal details to users
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": {
                "message": "A temporary system error occurred. Please try again later.",
                "type": "server_error",
                "code": infra_exc.code,
                "correlation_id": infra_exc.correlation_id,
            }
        },
    )


def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors.

    This is a catch-all handler for exceptions that don't match other handlers.
    These map to HTTP 500 Internal Server Error. Full details are logged but
    only a generic message is shown to users.

    Args:
        request: FastAPI request object
        exc: Exception that was raised

    Returns:
        JSONResponse with generic error message and HTTP 500 status
    """
    correlation_id = str(uuid.uuid4())

    logger.error(
        "Unexpected error: %s",
        str(exc),
        extra={"correlation_id": correlation_id, "path": request.url.path},
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "An unexpected error occurred. Please contact support if the problem persists.",
                "type": "server_error",
                "code": "INTERNAL_ERROR",
                "correlation_id": correlation_id,
            }
        },
    )


def authentication_error_handler(
    request: Request, exc: AuthenticationError | Exception
) -> JSONResponse:
    """Handle authentication failures.

    Maps to HTTP 401 Unauthorized with a ``WWW-Authenticate: Bearer`` header so
    clients know how to authenticate.

    Args:
        request: FastAPI request object
        exc: Authentication error exception

    Returns:
        JSONResponse with error details and HTTP 401 status
    """
    auth_exc = exc if isinstance(exc, AuthenticationError) else AuthenticationError()

    logger.info(
        "Authentication failed: %s",
        auth_exc.message,
        extra={"correlation_id": auth_exc.correlation_id, "path": request.url.path},
    )

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=auth_exc.to_dict(),
        headers={"WWW-Authenticate": "Bearer"},
    )


def service_overloaded_handler(
    request: Request, exc: ServiceOverloadedError | Exception
) -> JSONResponse:
    """Handle route-level concurrency-cap rejections.

    Maps to HTTP 503 Service Unavailable with a ``Retry-After`` header.

    Args:
        request: FastAPI request object
        exc: Service overloaded error exception

    Returns:
        JSONResponse with error details and HTTP 503 status
    """
    over_exc = (
        exc
        if isinstance(exc, ServiceOverloadedError)
        else ServiceOverloadedError(scope="unknown")
    )

    logger.warning(
        "Service overloaded: %s",
        over_exc.message,
        extra={"correlation_id": over_exc.correlation_id, "path": request.url.path},
    )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=over_exc.to_dict(),
        headers={"Retry-After": str(over_exc.retry_after)},
    )


def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded | Exception
) -> Response:
    """Handle slowapi rate-limit rejections.

    Maps to HTTP 429 Too Many Requests with an OpenAI-style error envelope and
    a ``Retry-After`` header (injected via the limiter when available).

    Args:
        request: FastAPI request object
        exc: Rate limit exceeded exception

    Returns:
        JSONResponse with error details and HTTP 429 status
    """
    correlation_id = str(uuid.uuid4())
    detail = getattr(exc, "detail", "")

    logger.info(
        "Rate limit exceeded: %s",
        detail,
        extra={"correlation_id": correlation_id, "path": request.url.path},
    )

    response: Response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": {
                "message": f"Rate limit exceeded: {detail}",
                "type": "rate_limit_error",
                "code": "RATE_LIMIT_EXCEEDED",
                "correlation_id": correlation_id,
            }
        },
    )

    limiter = getattr(request.app.state, "limiter", None)
    view_rate_limit = getattr(request.state, "view_rate_limit", None)
    if limiter is not None and view_rate_limit is not None:
        response = limiter._inject_headers(response, view_rate_limit)

    return response
