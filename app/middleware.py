"""Middleware for request handling, logging, and validation."""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .config import Config
from .logger import logger
from .request_context import generate_correlation_id, set_correlation_id, set_request_start_time


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to manage request context including correlation IDs and timing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process each request with context management.
        
        Args:
            request: The incoming request.
            call_next: The next middleware or endpoint handler.
            
        Returns:
            Response: The processed response.
        """
        # Generate or extract correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = generate_correlation_id()
        
        # Set context variables
        set_correlation_id(correlation_id)
        start_time = time.time()
        set_request_start_time(start_time)
        
        # Log request start
        logger.info(
            f"Request started: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log request completion
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"-> {response.status_code} in {duration:.3f}s"
            )
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"after {duration:.3f}s - {str(e)}"
            )
            raise


class FileSizeMiddleware(BaseHTTPMiddleware):
    """Middleware to validate file upload sizes before processing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Check file size limits for upload requests.
        
        Args:
            request: The incoming request.
            call_next: The next middleware or endpoint handler.
            
        Returns:
            Response: The processed response.
        """
        # Check if this is a file upload request
        if request.method in ["POST", "PUT"] and request.headers.get("content-type", "").startswith("multipart/form-data"):
            content_length = request.headers.get("content-length")
            
            if content_length:
                content_length = int(content_length)
                if content_length > Config.MAX_FILE_SIZE_BYTES:
                    max_size_mb = Config.MAX_FILE_SIZE_MB
                    current_size_mb = content_length / (1024 * 1024)
                    
                    logger.warning(
                        f"Request rejected: file size {current_size_mb:.2f}MB exceeds limit of {max_size_mb}MB"
                    )
                    
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=413,
                        detail=f"Request entity too large: {current_size_mb:.2f}MB exceeds maximum allowed size of {max_size_mb}MB"
                    )
        
        return await call_next(request)