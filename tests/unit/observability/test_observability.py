"""Unit tests for the optional OpenTelemetry instrumentation."""

import os
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider

import app.observability as observability
from app.core.config import Settings, get_settings
from app.observability.metrics import configure_metrics
from app.observability.tracing import build_resource, configure_tracing

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
    middleware_before = list(app.user_middleware)

    observability.configure_observability(app, _settings(OTEL__ENABLED="false"))

    assert list(app.user_middleware) == middleware_before
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
