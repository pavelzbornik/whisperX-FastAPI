"""OpenTelemetry metrics configuration for WhisperX FastAPI application."""

import logging

from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from prometheus_client import start_http_server

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def configure_metrics() -> None:
    """
    Configure OpenTelemetry metrics with Prometheus exporter.

    This function initializes the MeterProvider with a Prometheus metric reader
    and starts an HTTP server to expose metrics at the configured port.
    """
    settings = get_settings()

    # Skip configuration if observability or metrics are disabled
    if not settings.observability.OTEL_ENABLED:
        logger.info("OpenTelemetry metrics is disabled (observability disabled)")
        return

    if not settings.observability.OTEL_METRICS_ENABLED:
        logger.info("OpenTelemetry metrics is disabled")
        return

    try:
        # Create resource with service information
        resource_attributes = {
            "service.name": settings.observability.OTEL_SERVICE_NAME,
            "service.version": settings.observability.OTEL_SERVICE_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
        resource = Resource.create(resource_attributes)

        # Create Prometheus metric reader
        prometheus_reader = PrometheusMetricReader()

        # Create meter provider
        provider = MeterProvider(resource=resource, metric_readers=[prometheus_reader])
        metrics.set_meter_provider(provider)

        # Start Prometheus HTTP server
        metrics_port = settings.observability.OTEL_METRICS_PORT
        start_http_server(port=metrics_port, addr="0.0.0.0")

        logger.info(
            f"OpenTelemetry metrics configured with Prometheus exporter on port {metrics_port}"
        )

    except Exception as e:
        logger.warning(
            f"Failed to configure metrics: {e}. Metrics collection will be disabled."
        )


def get_meter(name: str) -> metrics.Meter:
    """
    Get a meter for instrumentation.

    Args:
        name: The name of the meter (typically __name__ of the calling module).

    Returns:
        A Meter instance for creating metrics.
    """
    return metrics.get_meter(name)


# Pre-defined metrics for common use cases
class Metrics:
    """Container for application metrics."""

    def __init__(self) -> None:
        """Initialize metrics."""
        settings = get_settings()
        if (
            not settings.observability.OTEL_ENABLED
            or not settings.observability.OTEL_METRICS_ENABLED
        ):
            # Create no-op meters if disabled
            self._meter = metrics.get_meter("noop")
        else:
            self._meter = get_meter("whisperx.api")

        # Audio processing metrics
        self.audio_processing_requests_total = self._meter.create_counter(
            name="audio_processing_requests_total",
            description="Total audio processing requests",
            unit="1",
        )

        self.audio_processing_duration_seconds = self._meter.create_histogram(
            name="audio_processing_duration_seconds",
            description="Audio processing duration",
            unit="s",
        )

        self.audio_file_size_bytes = self._meter.create_histogram(
            name="audio_file_size_bytes",
            description="Audio file size",
            unit="By",
        )

        self.audio_duration_seconds = self._meter.create_histogram(
            name="audio_duration_seconds",
            description="Audio duration in seconds",
            unit="s",
        )

        # ML operation metrics
        self.ml_model_loads_total = self._meter.create_counter(
            name="ml_model_loads_total",
            description="Total ML model loads",
            unit="1",
        )

        self.ml_inference_duration_seconds = self._meter.create_histogram(
            name="ml_inference_duration_seconds",
            description="ML inference duration",
            unit="s",
        )

        # Task metrics
        self.active_tasks = self._meter.create_up_down_counter(
            name="active_tasks",
            description="Number of active tasks",
            unit="1",
        )


# Global metrics instance
_metrics: Metrics | None = None


def get_metrics() -> Metrics:
    """
    Get the global metrics instance.

    Returns:
        The Metrics instance for recording application metrics.
    """
    global _metrics
    if _metrics is None:
        _metrics = Metrics()
    return _metrics
