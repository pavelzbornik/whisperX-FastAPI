"""OpenTelemetry tracing configuration for WhisperX FastAPI application."""

import logging
import socket
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def configure_tracing() -> None:
    """
    Configure OpenTelemetry tracing with OTLP exporter.

    This function initializes the TracerProvider with resource attributes,
    configures sampling strategy based on environment, and sets up the
    OTLP span exporter if an endpoint is configured.
    """
    settings = get_settings()

    # Skip configuration if observability is disabled
    if not settings.observability.OTEL_ENABLED:
        logger.info("OpenTelemetry tracing is disabled")
        return

    # Create resource with service information
    resource_attributes = {
        "service.name": settings.observability.OTEL_SERVICE_NAME,
        "service.version": settings.observability.OTEL_SERVICE_VERSION,
        "deployment.environment": settings.ENVIRONMENT,
        "host.name": socket.gethostname(),
    }

    # Add GPU availability to resource attributes
    try:
        import torch

        if torch.cuda.is_available():
            resource_attributes["gpu.available"] = "true"
            resource_attributes["gpu.count"] = str(torch.cuda.device_count())
            resource_attributes["gpu.device"] = str(settings.whisper.DEVICE.value)
        else:
            resource_attributes["gpu.available"] = "false"
    except ImportError:
        resource_attributes["gpu.available"] = "unknown"

    resource = Resource.create(resource_attributes)

    # Configure sampling strategy based on environment
    sample_rate = settings.otel_trace_sample_rate_computed
    sampler = ParentBasedTraceIdRatio(sample_rate)

    # Create tracer provider
    provider = TracerProvider(resource=resource, sampler=sampler)

    # Configure OTLP exporter if endpoint is provided
    otlp_endpoint = settings.observability.OTEL_EXPORTER_OTLP_ENDPOINT
    if otlp_endpoint:
        try:
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                insecure=settings.observability.OTEL_EXPORTER_OTLP_INSECURE,
            )
            # Use BatchSpanProcessor for efficient batching
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(
                f"OpenTelemetry tracing configured with OTLP endpoint: {otlp_endpoint}"
            )
        except Exception as e:
            logger.warning(
                f"Failed to configure OTLP exporter: {e}. Tracing will continue without export."
            )
    else:
        logger.info(
            "No OTLP endpoint configured. Traces will be generated but not exported."
        )

    # Set global tracer provider
    trace.set_tracer_provider(provider)

    logger.info(
        f"OpenTelemetry tracing initialized for {settings.observability.OTEL_SERVICE_NAME} "
        f"v{settings.observability.OTEL_SERVICE_VERSION} "
        f"(environment: {settings.ENVIRONMENT}, sample_rate: {sample_rate:.2%})"
    )


def get_tracer(name: str) -> trace.Tracer:
    """
    Get a tracer for instrumentation.

    Args:
        name: The name of the tracer (typically __name__ of the calling module).

    Returns:
        A Tracer instance for creating spans.
    """
    return trace.get_tracer(name)


def get_current_span() -> Optional[trace.Span]:
    """
    Get the current active span.

    Returns:
        The current span if one is active, None otherwise.
    """
    span = trace.get_current_span()
    return span if span.is_recording() else None


def get_trace_context() -> dict[str, str]:
    """
    Get the current trace context as a dictionary.

    Returns:
        Dictionary containing trace_id and span_id, or empty dict if no active span.
    """
    span = get_current_span()
    if span:
        ctx = span.get_span_context()
        return {
            "trace_id": format(ctx.trace_id, "032x"),
            "span_id": format(ctx.span_id, "016x"),
        }
    return {}
