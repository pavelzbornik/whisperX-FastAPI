"""Optional OpenTelemetry instrumentation.

Everything here is a no-op unless ``OTEL__ENABLED`` is set, so importing this
package costs nothing at runtime beyond the import itself.

Entry points are :func:`configure_observability`, called once during startup,
and :func:`shutdown_observability`, called during shutdown so buffered spans
and metrics are flushed rather than dropped.
"""

import logging

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider

from app.core.config import Settings, get_settings
from app.observability.metrics import configure_metrics
from app.observability.tracing import configure_tracing

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None

# Traced separately would be noise: these are polled by orchestrators and would
# swamp the trace volume without saying anything about real traffic.
_EXCLUDED_URLS = "health,health/ready,health/live,metrics"


def configure_observability(app: FastAPI, settings: Settings | None = None) -> None:
    """Set up tracing, metrics, and auto-instrumentation for *app*.

    Safe to call when observability is disabled — it returns immediately
    without touching global OpenTelemetry state.

    Args:
        app: The FastAPI application to instrument.
        settings: Application settings; read from the cache when omitted.
    """
    global _tracer_provider, _meter_provider

    settings = settings or get_settings()
    if not settings.observability.ENABLED:
        logger.debug("OpenTelemetry disabled; skipping instrumentation")
        return

    _tracer_provider = configure_tracing(settings)
    _meter_provider = configure_metrics(settings)

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=_tracer_provider,
        meter_provider=_meter_provider,
        excluded_urls=_EXCLUDED_URLS,
    )

    # Instrumenting the engines rather than passing one engine covers both the
    # async request path and the sync background-task path.
    SQLAlchemyInstrumentor().instrument(tracer_provider=_tracer_provider)

    logger.info("OpenTelemetry instrumentation active")


def shutdown_observability() -> None:
    """Flush and shut down any providers installed at startup."""
    global _tracer_provider, _meter_provider

    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        _tracer_provider = None

    if _meter_provider is not None:
        _meter_provider.shutdown()
        _meter_provider = None


__all__ = ["configure_observability", "shutdown_observability"]
