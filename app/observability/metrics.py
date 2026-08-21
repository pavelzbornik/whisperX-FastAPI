"""OpenTelemetry metrics setup.

Metrics are pushed to the collector over OTLP on a timer. Nothing here opens a
listening socket — a scrape endpoint would mean a second bound port that the
container does not expose.
"""

import logging

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

from app.core.config import Settings
from app.observability.tracing import build_resource

logger = logging.getLogger(__name__)


def configure_metrics(settings: Settings) -> MeterProvider | None:
    """Install a meter provider exporting over OTLP/HTTP.

    Args:
        settings: Application settings.

    Returns:
        The provider that was installed, or ``None`` when metrics are disabled.
    """
    if not settings.observability.ENABLED or not settings.observability.METRICS_ENABLED:
        return None

    # As in tracing: an empty endpoint defers to the SDK's own env var.
    endpoint = settings.observability.EXPORTER_ENDPOINT
    exporter = (
        OTLPMetricExporter(endpoint=endpoint) if endpoint else OTLPMetricExporter()
    )
    reader = PeriodicExportingMetricReader(
        exporter,
        export_interval_millis=settings.observability.METRICS_EXPORT_INTERVAL_MS,
    )

    provider = MeterProvider(resource=build_resource(settings), metric_readers=[reader])
    metrics.set_meter_provider(provider)
    logger.info(
        "OpenTelemetry metrics enabled (export interval %dms)",
        settings.observability.METRICS_EXPORT_INTERVAL_MS,
    )
    return provider
