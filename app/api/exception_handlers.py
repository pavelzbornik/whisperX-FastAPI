"""Exception handlers for FastAPI application.

This module defines handlers that map domain exceptions to HTTP responses,
ensuring consistent error formatting and proper separation of concerns.
"""

import logging
import uuid
from typing import Union

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.api.middleware.request_id import get_request_id
from app.core.exceptions import (
    DomainError,
    InfrastructureError,
    TaskNotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)


async def domain_error_handler(
    request: Request, exc: Union[DomainError, Exception]
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

    # Get request ID from middleware context
    request_id = get_request_id()

    logger.warning(
        "Domain error: %s",
        domain_exc.message,
        extra={
            "correlation_id": domain_exc.correlation_id,
            "request_id": request_id,
            "code": domain_exc.code,
            "path": request.url.path,
        },
    )

    error_response = domain_exc.to_dict()
    error_response["request_id"] = request_id

    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=error_response)


async def validation_error_handler(
    request: Request, exc: Union[ValidationError, Exception]
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

    # Get request ID from middleware context
    request_id = get_request_id()

    logger.info(
        "Validation error: %s",
        val_exc.message,
        extra={
            "correlation_id": val_exc.correlation_id,
            "request_id": request_id,
            "path": request.url.path,
        },
    )

    error_response = val_exc.to_dict()
    error_response["request_id"] = request_id

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_response
    )


async def task_not_found_handler(
    request: Request, exc: Union[TaskNotFoundError, Exception]
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

    # Get request ID from middleware context
    request_id = get_request_id()

    logger.info(
        "Task not found: %s",
        task_exc.details.get("identifier"),
        extra={
            "correlation_id": task_exc.correlation_id,
            "request_id": request_id,
            "path": request.url.path,
        },
    )

    error_response = task_exc.to_dict()
    error_response["request_id"] = request_id

    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=error_response)


async def infrastructure_error_handler(
    request: Request, exc: Union[InfrastructureError, Exception]
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

    # Get request ID from middleware context
    request_id = get_request_id()

    logger.error(
        "Infrastructure error: %s",
        infra_exc.message,
        extra={
            "correlation_id": infra_exc.correlation_id,
            "request_id": request_id,
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
                "code": infra_exc.code,
                "correlation_id": infra_exc.correlation_id,
                "request_id": request_id,
            }
        },
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
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
    request_id = get_request_id()

    logger.error(
        "Unexpected error: %s",
        str(exc),
        extra={
            "correlation_id": correlation_id,
            "request_id": request_id,
            "path": request.url.path,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "An unexpected error occurred. Please contact support if the problem persists.",
                "code": "INTERNAL_ERROR",
                "correlation_id": correlation_id,
                "request_id": request_id,
            }
        },
    )
