"""API Version 1 - All v1 endpoints."""

from app.api.v1.audio_api import router as audio_router
from app.api.v1.audio_services_api import router as service_router
from app.api.v1.task_api import router as task_router

__all__ = ["audio_router", "service_router", "task_router"]
