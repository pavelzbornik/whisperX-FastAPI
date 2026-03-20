"""Main entry point for the FastAPI application."""

from collections.abc import AsyncGenerator, MutableMapping

from app.core.warnings_filter import filter_warnings

filter_warnings()

# PyTorch 2.6 changed torch.load default to weights_only=True, which breaks
# speechbrain/pyannote model loading (used by WhisperX diarization and VAD).
# These models are loaded from trusted HuggingFace sources, so we restore the
# pre-2.6 default of weights_only=False for callers that don't set it explicitly.
import functools  # noqa: E402
from typing import Any  # noqa: E402

import torch  # noqa: E402

_original_torch_load = torch.load


@functools.wraps(_original_torch_load)
def _torch_load_compat(*args: Any, **kwargs: Any) -> Any:
    """Wrap torch.load to default weights_only=False for trusted model files.

    PyTorch 2.6 treats weights_only=None as "not set" and defaults to True.
    lightning_fabric (used by pyannote) passes weights_only=None explicitly,
    so we must intercept None as well as missing to restore the pre-2.6 default.
    """
    if kwargs.get("weights_only") is not True:
        kwargs["weights_only"] = False
    return _original_torch_load(*args, **kwargs)


torch.load = _torch_load_compat

import logging  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from dotenv import load_dotenv  # noqa: E402
from fastapi import FastAPI, status  # noqa: E402
from fastapi.responses import JSONResponse, RedirectResponse  # noqa: E402
from sqlalchemy import text  # noqa: E402
from starlette.types import ASGIApp, Receive, Scope, Send  # noqa: E402

# Load environment variables from .env early
load_dotenv()

# Initialize logging configuration as early as possible
from app.core.logging import configure_logging  # noqa: E402

configure_logging()

from app.core.logging.context import (  # noqa: E402
    endpoint_var,
    ip_address_var,
    request_id_var,
)

# Get logger for application startup
logger = logging.getLogger("app")

from app.api import service_router, stt_router, task_router  # noqa: E402
from app.api.exception_handlers import (  # noqa: E402
    domain_error_handler,
    generic_error_handler,
    infrastructure_error_handler,
    task_not_found_handler,
    validation_error_handler,
)
from app.core.config import Config  # noqa: E402
from app.core.container import Container  # noqa: E402
from app.core.exceptions import (  # noqa: E402
    DomainError,
    InfrastructureError,
    TaskNotFoundError,
    ValidationError,
)
from app.docs import generate_db_schema, save_openapi_json  # noqa: E402
from app.infrastructure.database import Base, async_engine, sync_engine  # noqa: E402

# Log application startup information
environment = os.getenv("ENVIRONMENT", "production").lower()
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger.info("Starting whisperX FastAPI application")
logger.info("Environment: %s", environment)
logger.info("Log level: %s", log_level)
logger.info("Device: %s", Config.DEVICE)
logger.info("Compute type: %s", Config.COMPUTE_TYPE)
logger.info("Whisper model: %s", Config.WHISPER_MODEL)

# Create dependency injection container
container = Container()

# Set container in dependencies module
from app.api import dependencies  # noqa: E402

dependencies.set_container(container)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for the FastAPI application.

    This function is used to perform startup and shutdown tasks for the FastAPI application.
    It saves the OpenAPI JSON and generates the database schema.

    Args:
        app (FastAPI): The FastAPI application instance.
    """
    logger.info("Application lifespan started - dependency container initialized")

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database connection established")

    save_openapi_json(app)
    generate_db_schema(Base.metadata.tables.values())
    logger.info("OpenAPI schema and database schema documentation generated")

    yield

    # Clean up container on shutdown
    logger.info("Shutting down application")
    # Dispose both engine pools so connections are not reused across event loops
    # (e.g. between test modules that each create a TestClient context).
    # sync_engine uses QueuePool for PostgreSQL; disposing prevents connection leaks.
    await async_engine.dispose()
    sync_engine.dispose()


tags_metadata = [
    {
        "name": "Speech-2-Text",
        "description": "Operations related to transcript",
    },
    {
        "name": "Speech-2-Text services",
        "description": "Individual services for transcript",
    },
    {
        "name": "Tasks Management",
        "description": "Manage tasks.",
    },
    {
        "name": "Health",
        "description": "Health check endpoints to monitor application status",
    },
]


app = FastAPI(
    title="whisperX REST service",
    description=f"""
    # whisperX RESTful API

    Welcome to the whisperX RESTful API! This API provides a suite of audio processing services to enhance and analyze your audio content.

    ## Documentation:

    For detailed information on request and response formats, consult the [WhisperX Documentation](https://github.com/m-bain/whisperX).

    ## Services:

    Speech-2-Text provides a suite of audio processing services to enhance and analyze your audio content. The following services are available:

    1. Transcribe: Transcribe an audio/video  file into text.
    2. Align: Align the transcript to the audio/video file.
    3. Diarize: Diarize an audio/video file into speakers.
    4. Combine Transcript and Diarization: Combine the transcript and diarization results.

    ## Supported file extensions:
    AUDIO_EXTENSIONS = {Config.AUDIO_EXTENSIONS}

    VIDEO_EXTENSIONS = {Config.VIDEO_EXTENSIONS}

    """,
    version="0.0.1",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

# Register exception handlers
app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
app.add_exception_handler(ValidationError, validation_error_handler)
app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(InfrastructureError, infrastructure_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# Include routers
app.include_router(stt_router)
app.include_router(task_router)
app.include_router(service_router)


class RequestContextMiddleware:
    """Pure ASGI middleware that sets request-scoped context vars.

    Implemented as a raw ASGI middleware (not ``BaseHTTPMiddleware``) to
    guarantee correct ``contextvars`` propagation to downstream handlers
    and background tasks.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialise with the wrapped ASGI application.

        Args:
            app: The next ASGI application in the stack.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Set context vars for HTTP requests, then call the inner app.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        rid = headers.get(b"x-request-id", b"").decode() or str(uuid.uuid4())
        request_id_var.set(rid)

        client = scope.get("client")
        ip_address_var.set(client[0] if client else "unknown")
        endpoint_var.set(scope.get("path", ""))

        async def send_with_request_id(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", rid.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_request_id)


app.add_middleware(RequestContextMiddleware)


@app.get("/", include_in_schema=False)
async def index() -> RedirectResponse:
    """Redirect to the documentation."""
    return RedirectResponse(url="/docs", status_code=307)


# Health check endpoints
@app.get("/health", tags=["Health"], summary="Simple health check")
async def health_check() -> JSONResponse:
    """Verify the service is up and running.

    Returns a simple status response to confirm the API service is operational.
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ok", "message": "Service is running"},
    )


@app.get("/health/live", tags=["Health"], summary="Liveness check")
async def liveness_check() -> JSONResponse:
    """Check if the application is running.

    Used by orchestration systems like Kubernetes to detect if the app is alive.
    Returns timestamp along with status information.
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ok",
            "timestamp": time.time(),
            "message": "Application is live",
        },
    )


@app.get("/health/ready", tags=["Health"], summary="Readiness check")
async def readiness_check() -> JSONResponse:
    """Check if the application is ready to accept requests.

    Verifies dependencies like the database are connected and ready.
    Returns HTTP 200 if all systems are operational, HTTP 503 if any dependency
    has failed.
    """
    try:
        # Check database connection
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ok",
                "database": "connected",
                "message": "Application is ready to accept requests",
            },
        )
    except Exception:
        logger.exception("Readiness check failed:")

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "database": "disconnected",
                "message": "Application is not ready due to an internal error.",
            },
        )
