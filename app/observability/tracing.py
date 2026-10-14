"""OpenTelemetry tracing setup.

Tracing is opt-in. When ``OTEL__ENABLED`` is false nothing here touches global
state, so the application keeps behaving exactly as it did before.
"""

import logging
from importlib.metadata import PackageNotFoundError, version
from urllib.parse import urlsplit, urlunsplit

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

from app.core.config import Settings

logger = logging.getLogger(__name__)


def _signal_endpoint(endpoint: str, signal: str) -> str:
    """Resolve an OTLP/HTTP endpoint to its signal-specific URL.

    An explicit ``endpoint=`` is sent verbatim by the exporters, unlike the
    SDK's own ``OTEL_EXPORTER_OTLP_ENDPOINT``, which is treated as a base and
    gets the signal path appended. Configuring a bare collector URL — which is
    what the documentation asks for — would therefore POST both traces and
    metrics to the collector root, where they are dropped.

    A URL that already carries a path is left untouched: that is the operator
    naming a specific ingest route, and second-guessing it would break gateways
    that do not use the conventional layout.

    Args:
        endpoint: The configured OTLP/HTTP endpoint. Assumed non-empty.
        signal: The OTLP signal name, ``traces`` or ``metrics``.

    Returns:
        The endpoint the exporter should post to.
    """
    parts = urlsplit(endpoint)

    # Only the path component decides. A lone "/" is the collector root, not a
    # route the operator chose, so it still gets the signal path.
    if parts.path.strip("/"):
        return endpoint

    # Rebuilt from the parsed parts rather than concatenated, so the path lands
    # ahead of any query or fragment. Appending textually to a URL like
    # "http://collector:4318?tenant=foo" would bury "/v1/traces" inside the
    # query value and post to the collector root.
    return urlunsplit(parts._replace(path=f"/v1/{signal}"))


def _service_version() -> str:
    """Return the installed package version, or ``unknown`` if unavailable."""
    try:
        return version("whisperx-fastapi")
    except PackageNotFoundError:  # pragma: no cover - only when run from source
        return "unknown"


def build_resource(settings: Settings) -> Resource:
    """Describe this service for the collector.

    Args:
        settings: Application settings.

    Returns:
        Resource carrying service name, version, and deployment environment.
    """
    return Resource.create(
        {
            "service.name": settings.observability.SERVICE_NAME,
            "service.version": _service_version(),
            "deployment.environment": settings.ENVIRONMENT,
        }
    )


def configure_tracing(settings: Settings) -> TracerProvider | None:
    """Install a tracer provider exporting over OTLP/HTTP.

    Args:
        settings: Application settings.

    Returns:
        The provider that was installed, or ``None`` when tracing is disabled.
    """
    if not settings.observability.ENABLED:
        return None

    provider = TracerProvider(
        resource=build_resource(settings),
        sampler=ParentBasedTraceIdRatio(settings.observability.TRACES_SAMPLER_RATIO),
    )

    # An empty endpoint is deliberate — the exporter then reads the SDK's own
    # OTEL_EXPORTER_OTLP_ENDPOINT, so existing collector config keeps working.
    endpoint = settings.observability.EXPORTER_ENDPOINT
    exporter = (
        OTLPSpanExporter(endpoint=_signal_endpoint(endpoint, "traces"))
        if endpoint
        else OTLPSpanExporter()
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    logger.info(
        "OpenTelemetry tracing enabled (sampler ratio %.2f)",
        settings.observability.TRACES_SAMPLER_RATIO,
    )
    return provider
