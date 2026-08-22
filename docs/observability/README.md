# Observability

The service can emit OpenTelemetry traces and metrics to an OTLP collector. It is **off by
default** — with `OTEL__ENABLED` unset, no provider is installed, no instrumentation is
applied, and nothing is exported.

## Enabling

```bash
OTEL__ENABLED=true
OTEL__EXPORTER_ENDPOINT=http://collector:4318   # OTLP/HTTP base endpoint
```

Leaving `OTEL__EXPORTER_ENDPOINT` empty is supported and useful: the exporters then fall
back to the SDK's own standard variables (`OTEL_EXPORTER_OTLP_ENDPOINT`,
`OTEL_EXPORTER_OTLP_HEADERS`, …), so an existing collector setup keeps working untouched.

| Variable | Default | Meaning |
| --- | --- | --- |
| `OTEL__ENABLED` | `false` | Master switch for tracing and metrics |
| `OTEL__SERVICE_NAME` | `whisperx-fastapi` | Reported as `service.name` |
| `OTEL__EXPORTER_ENDPOINT` | *(empty)* | OTLP/HTTP endpoint; empty defers to the SDK |
| `OTEL__TRACES_SAMPLER_RATIO` | `1.0` | Sampled fraction when there is no parent decision |
| `OTEL__METRICS_ENABLED` | `true` | Export metrics too (only when `OTEL__ENABLED`) |
| `OTEL__METRICS_EXPORT_INTERVAL_MS` | `60000` | How often metrics are pushed |

## What is instrumented

- **HTTP** — via `FastAPIInstrumentor`: one span per request, with route, method, and
  status. The health endpoints are excluded; orchestrators poll them constantly and the
  spans say nothing about real traffic.
- **Database** — via `SQLAlchemyInstrumentor`, covering both the async request path and the
  sync background-task path.

Spans carry the same `request_id` the logs do, so a trace can be lined up with its log
records.

## Transport

Traces and metrics both go out over **OTLP/HTTP**. Two deliberate choices here:

- **HTTP, not gRPC** — the gRPC exporter drags in `grpcio`, a large binary wheel, for no
  benefit at this volume.
- **Push, not scrape** — a Prometheus scrape endpoint would mean binding a second port
  that the container does not expose. Metrics are pushed to the collector on a timer
  instead; scrape it there if Prometheus is the destination.

Providers are shut down during application shutdown so buffered spans and metrics are
flushed rather than dropped.

## Sampling

`OTEL__TRACES_SAMPLER_RATIO` uses a parent-based ratio sampler: an incoming sampling
decision is respected, and only root spans are subject to the ratio. Transcription requests
are long and low-volume, so `1.0` is usually fine; lower it if the API fronts something
chattier.
