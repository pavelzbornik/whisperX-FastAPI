"""Main entry point for the FastAPI application."""

from .warnings_filter import filter_warnings

filter_warnings()

import os
import psutil
import time  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from dotenv import load_dotenv  # noqa: E402
from fastapi import FastAPI, status  # noqa: E402
from fastapi.responses import JSONResponse, RedirectResponse  # noqa: E402
from sqlalchemy import text  # noqa: E402

from .config import Config  # noqa: E402
from .db import engine  # noqa: E402
from .docs import generate_db_schema, save_openapi_json  # noqa: E402
from .middleware import FileSizeMiddleware, RequestContextMiddleware  # noqa: E402
from .models import Base  # noqa: E402
from .request_context import generate_correlation_id, set_correlation_id  # noqa: E402
from .routers import stt, stt_services, task  # noqa: E402

# Load environment variables from .env
load_dotenv()

Base.metadata.create_all(bind=engine)


# Global variable to track application start time
start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.

    This function is used to perform startup and shutdown tasks for the FastAPI application.
    It saves the OpenAPI JSON and generates the database schema.

    Args:
        app (FastAPI): The FastAPI application instance.
    """
    global start_time
    start_time = time.time()
    save_openapi_json(app)
    generate_db_schema(Base.metadata.tables.values())
    yield


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

# Add middleware (order matters: last added = first executed)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(FileSizeMiddleware)

# Include routers
app.include_router(stt.stt_router)
app.include_router(task.task_router)
app.include_router(stt_services.service_router)


@app.get("/", include_in_schema=False)
async def index():
    """Redirect to the documentation."""
    return RedirectResponse(url="/docs", status_code=307)


def get_gpu_info():
    """Get GPU information if available."""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_info = []
            for i in range(gpu_count):
                props = torch.cuda.get_device_properties(i)
                memory_used = torch.cuda.memory_allocated(i)
                memory_total = props.total_memory
                memory_free = memory_total - memory_used
                
                gpu_info.append({
                    "device_id": i,
                    "name": props.name,
                    "memory_used_mb": round(memory_used / 1024 / 1024, 2),
                    "memory_total_mb": round(memory_total / 1024 / 1024, 2),
                    "memory_free_mb": round(memory_free / 1024 / 1024, 2),
                    "memory_usage_percent": round((memory_used / memory_total) * 100, 2),
                })
            return {"available": True, "devices": gpu_info}
        else:
            return {"available": False, "reason": "CUDA not available"}
    except ImportError:
        return {"available": False, "reason": "PyTorch not available"}
    except Exception as e:
        return {"available": False, "reason": f"Error: {str(e)}"}


def get_system_metrics():
    """Get system resource metrics."""
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "cpu_count": psutil.cpu_count(),
            "memory": {
                "total_mb": round(memory.total / 1024 / 1024, 2),
                "used_mb": round(memory.used / 1024 / 1024, 2),
                "available_mb": round(memory.available / 1024 / 1024, 2),
                "usage_percent": memory.percent,
            },
            "disk": {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "usage_percent": round((disk.used / disk.total) * 100, 2),
            }
        }
    except Exception as e:
        return {"error": f"Failed to get system metrics: {str(e)}"}


# Health check endpoints
@app.get("/health", tags=["Health"], summary="Simple health check")
async def health_check():
    """Verify the service is up and running.

    Returns a simple status response to confirm the API service is operational.
    """
    correlation_id = generate_correlation_id()
    set_correlation_id(correlation_id)
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ok", 
            "message": "Service is running",
            "correlation_id": correlation_id,
            "timestamp": time.time(),
        },
    )


@app.get("/health/live", tags=["Health"], summary="Liveness check")
async def liveness_check():
    """Check if the application is running.

    Used by orchestration systems like Kubernetes to detect if the app is alive.
    Returns timestamp along with status information.
    """
    correlation_id = generate_correlation_id()
    set_correlation_id(correlation_id)
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ok",
            "timestamp": time.time(),
            "message": "Application is live",
            "correlation_id": correlation_id,
            "uptime_seconds": time.time() - start_time,
        },
    )


@app.get("/health/ready", tags=["Health"], summary="Readiness check")
async def readiness_check():
    """Check if the application is ready to accept requests.

    Verifies dependencies like the database are connected and ready.
    Returns HTTP 200 if all systems are operational, HTTP 503 if any dependency
    has failed.
    """
    correlation_id = generate_correlation_id()
    set_correlation_id(correlation_id)
    
    health_status = {
        "status": "ok",
        "timestamp": time.time(),
        "correlation_id": correlation_id,
        "components": {},
        "system_metrics": get_system_metrics(),
        "gpu_info": get_gpu_info(),
    }
    
    # Check database connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        health_status["components"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
    
    # Check if running in acceptable resource limits
    system_metrics = health_status["system_metrics"]
    if not isinstance(system_metrics, dict) or "error" in system_metrics:
        health_status["components"]["system_resources"] = {
            "status": "unknown",
            "message": "Unable to determine system resource status"
        }
    else:
        memory_usage = system_metrics.get("memory", {}).get("usage_percent", 0)
        cpu_usage = system_metrics.get("cpu_percent", 0)
        disk_usage = system_metrics.get("disk", {}).get("usage_percent", 0)
        
        if memory_usage > 90 or cpu_usage > 95 or disk_usage > 95:
            health_status["status"] = "degraded"
            health_status["components"]["system_resources"] = {
                "status": "warning",
                "message": f"High resource usage - CPU: {cpu_usage}%, Memory: {memory_usage}%, Disk: {disk_usage}%"
            }
        else:
            health_status["components"]["system_resources"] = {
                "status": "healthy",
                "message": "System resources within acceptable limits"
            }
    
    # Determine overall HTTP status
    if health_status["status"] == "ok":
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=health_status,
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health_status,
        )
