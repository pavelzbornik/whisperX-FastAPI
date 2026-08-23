"""Unit tests for the optional OpenTelemetry instrumentation."""

import os
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider

import app.observability as observability
from app.core.config import Settings, get_settings
from app.observability.metrics import configure_metrics
from app.observability.tracing import (
    _signal_endpoint,
    build_resource,
    configure_tracing,
)

_ENV_KEYS = (
    "OTEL__ENABLED",
    "OTEL__METRICS_ENABLED",
    "OTEL__EXPORTER_ENDPOINT",
    "OTEL__TRACES_SAMPLER_RATIO",
    "OTEL__SERVICE_NAME",
)


@pytest.fixture(autouse=True)
def reset_otel_env() -> Generator[None, None, None]:
    """Restore observability env vars and the settings cache after each test."""
    get_settings.cache_clear()
    originals = {key: os.environ.get(key) for key in _ENV_KEYS}
    yield
    for key, value in originals.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


def _settings(**env: str) -> Settings:
    """Build a Settings instance from the given observability env overrides."""
    for key, value in env.items():
        os.environ[key] = value
    get_settings.cache_clear()
    return get_settings()


@pytest.mark.unit
def test_disabled_by_default() -> None:
    """Observability stays off unless explicitly enabled."""
    os.environ.pop("OTEL__ENABLED", None)
    get_settings.cache_clear()

    assert get_settings().observability.ENABLED is False


@pytest.mark.unit
def test_configure_tracing_returns_none_when_disabled() -> None:
    """No tracer provider is built while observability is off."""
    assert configure_tracing(_settings(OTEL__ENABLED="false")) is None


@pytest.mark.unit
def test_configure_metrics_returns_none_when_disabled() -> None:
    """No meter provider is built while observability is off."""
    assert configure_metrics(_settings(OTEL__ENABLED="false")) is None


@pytest.mark.unit
def test_configure_metrics_returns_none_when_only_metrics_disabled() -> None:
    """Metrics can be turned off independently of tracing."""
    settings = _settings(OTEL__ENABLED="true", OTEL__METRICS_ENABLED="false")

    assert configure_metrics(settings) is None


@pytest.mark.unit
def test_configure_observability_is_inert_when_disabled() -> None:
    """A disabled app is left completely uninstrumented.

    This is the property that keeps the feature safe to ship on by default:
    no middleware is added and no global provider is installed.
    """
    app = FastAPI()

    observability.configure_observability(app, _settings(OTEL__ENABLED="false"))

    # instrument_app wraps build_middleware_stack and sets this flag rather than
    # appending to user_middleware, so this is what actually proves it ran.
    assert getattr(app, "_is_instrumented_by_opentelemetry", False) is False
    assert observability._tracer_provider is None
    assert observability._meter_provider is None


@pytest.mark.unit
def test_resource_carries_service_identity() -> None:
    """The resource reports the configured service name and environment."""
    settings = _settings(OTEL__ENABLED="true", OTEL__SERVICE_NAME="custom-name")

    attributes = build_resource(settings).attributes

    assert attributes["service.name"] == "custom-name"
    assert attributes["deployment.environment"] == settings.ENVIRONMENT
    assert attributes["service.version"]


@pytest.mark.unit
def test_sampler_ratio_is_validated() -> None:
    """A ratio outside 0..1 is rejected rather than silently clamped."""
    with pytest.raises(ValueError):
        _settings(OTEL__ENABLED="true", OTEL__TRACES_SAMPLER_RATIO="1.5")


@pytest.mark.unit
def test_enabled_tracing_builds_provider() -> None:
    """Enabling observability produces a real tracer provider."""
    settings = _settings(
        OTEL__ENABLED="true",
        OTEL__EXPORTER_ENDPOINT="http://localhost:4318/v1/traces",
    )

    provider = configure_tracing(settings)
    try:
        assert isinstance(provider, TracerProvider)
    finally:
        if provider is not None:
            provider.shutdown()


@pytest.mark.unit
def test_enabled_metrics_builds_provider() -> None:
    """Enabling observability produces a real meter provider."""
    settings = _settings(
        OTEL__ENABLED="true",
        OTEL__EXPORTER_ENDPOINT="http://localhost:4318/v1/metrics",
    )

    provider = configure_metrics(settings)
    try:
        assert isinstance(provider, MeterProvider)
    finally:
        if provider is not None:
            provider.shutdown()


@pytest.mark.unit
def test_shutdown_is_safe_when_nothing_was_configured() -> None:
    """Shutdown on an uninstrumented app does not raise."""
    observability._tracer_provider = None
    observability._meter_provider = None

    observability.shutdown_observability()

    assert observability._tracer_provider is None
    assert observability._meter_provider is None


@pytest.mark.unit
def test_configure_observability_instruments_app_when_enabled() -> None:
    """Enabling observability installs providers and instruments the app.

    Instrumentation is global, so this test unwinds it again — otherwise later
    tests would run against a half-instrumented process.
    """
    app = FastAPI()
    settings = _settings(
        OTEL__ENABLED="true",
        OTEL__EXPORTER_ENDPOINT="http://localhost:4318",
    )

    try:
        observability.configure_observability(app, settings)

        assert isinstance(observability._tracer_provider, TracerProvider)
        assert isinstance(observability._meter_provider, MeterProvider)
        assert getattr(app, "_is_instrumented_by_opentelemetry", False) is True
    finally:
        FastAPIInstrumentor.uninstrument_app(app)
        SQLAlchemyInstrumentor().uninstrument()
        observability.shutdown_observability()

    assert observability._tracer_provider is None
    assert observability._meter_provider is None


@pytest.mark.unit
def test_configure_observability_reads_cached_settings_when_omitted() -> None:
    """Omitting settings falls back to get_settings() rather than raising."""
    app = FastAPI()
    _settings(OTEL__ENABLED="false")

    observability.configure_observability(app)

    assert observability._tracer_provider is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("http://collector:4318", "http://collector:4318/v1/traces"),
        ("http://collector:4318/", "http://collector:4318/v1/traces"),
        # An explicit path is the operator's choice and is left alone.
        ("http://collector:4318/v1/traces", "http://collector:4318/v1/traces"),
        ("http://gateway/custom/ingest", "http://gateway/custom/ingest"),
    ],
)
def test_traces_endpoint_gets_the_signal_path(configured: str, expected: str) -> None:
    """A bare collector URL must reach /v1/traces, not the collector root.

    The exporter uses an explicit ``endpoint`` verbatim, so a base URL -- which
    is exactly what the documentation tells operators to configure -- would
    otherwise POST spans to the collector root and be dropped.
    """
    assert _signal_endpoint(configured, "traces") == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("http://collector:4318", "http://collector:4318/v1/metrics"),
        ("http://collector:4318/v1/metrics", "http://collector:4318/v1/metrics"),
    ],
)
def test_metrics_endpoint_gets_the_signal_path(configured: str, expected: str) -> None:
    """Metrics resolve to their own path, not the same URL as traces."""
    assert _signal_endpoint(configured, "metrics") == expected


@pytest.mark.unit
def test_traces_and_metrics_do_not_share_one_endpoint() -> None:
    """One configured base must fan out to two distinct signal endpoints."""
    base = "http://collector:4318"

    assert _signal_endpoint(base, "traces") != _signal_endpoint(base, "metrics")
