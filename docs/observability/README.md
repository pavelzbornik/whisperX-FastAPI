# Observability with OpenTelemetry

## Overview

WhisperX FastAPI is fully instrumented with OpenTelemetry to provide comprehensive observability through distributed tracing, metrics, and structured logging.

## Quick Start

### 1. Configuration

Create or update `.env` file:

```bash
# Enable observability
observability__OTEL_ENABLED=true

# Configure OTLP exporter (optional, for Jaeger/Zipkin)
observability__OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Enable metrics
observability__OTEL_METRICS_ENABLED=true
observability__OTEL_METRICS_PORT=9090

# Set environment for sampling
ENVIRONMENT=development  # 100% sampling
# or
ENVIRONMENT=production   # 10% sampling (configurable)
```

### 2. Run with Observability Stack

#### Option A: Local Development (Metrics Only)

```bash
# Start application
uvicorn app.main:app --reload

# Access metrics
curl http://localhost:9090/metrics
```

#### Option B: Full Stack with Docker Compose

Create `docker-compose.observability.yml`:

```yaml
version: '3.8'

services:
  # Your application
  whisperx-api:
    build: .
    ports:
      - "8000:8000"
      - "9090:9090"  # Metrics
    environment:
      - observability__OTEL_ENABLED=true
      - observability__OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
      - observability__OTEL_METRICS_ENABLED=true
    depends_on:
      - jaeger
      - prometheus

  # Jaeger for traces
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP
    environment:
      - COLLECTOR_OTLP_ENABLED=true

  # Prometheus for metrics
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9091:9090"  # Prometheus UI
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  # Grafana for dashboards
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
```

Create `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'whisperx-api'
    static_configs:
      - targets: ['whisperx-api:9090']
```

Start the stack:

```bash
docker-compose -f docker-compose.observability.yml up -d
```

### 3. Access Observability Tools

- **Application**: <http://localhost:8000>
- **Jaeger UI**: <http://localhost:16686>
- **Prometheus**: <http://localhost:9091>
- **Grafana**: <http://localhost:3000> (admin/admin)
- **Metrics Endpoint**: <http://localhost:9090/metrics>

## Features

### Distributed Tracing

✅ Automatic HTTP request instrumentation
✅ Automatic database query instrumentation
✅ Custom spans for audio processing operations
✅ Custom spans for ML inference with detailed attributes
✅ Trace context propagation through background tasks
✅ Span events for key lifecycle milestones
✅ Exception recording in spans

**Key Spans**:

- `audio.validate_and_save` - File upload and validation
- `audio.load_and_validate` - Audio loading and duration calculation
- `audio_processing.*` - Background task processing
- `ml.transcribe` - Transcription with model loading, inference timing
- Database queries with SQL in comments

[Learn more about tracing →](./tracing.md)

### Metrics

✅ Request counters by status and task type
✅ Processing duration histograms
✅ File size and audio duration distributions
✅ ML model load counters
✅ ML inference duration histograms
✅ Active task gauges
✅ Prometheus-compatible export

**Key Metrics**:

- `audio_processing_requests_total` - Request counter
- `audio_processing_duration_seconds` - Duration histogram
- `ml_inference_duration_seconds` - ML operation timing
- `active_tasks` - Current task count

[Learn more about metrics →](./metrics.md)

### Structured Logging

✅ Trace context in all log messages
✅ Automatic trace_id and span_id injection
✅ Correlation between logs and traces

**Log Format**:

```
2025-10-25 18:04:45,172 [INFO] trace_id=a1b2c3d4... span_id=1234... app.api: Message
```

## Example Queries

### Tracing Queries (Jaeger)

Find slow requests:

```
service="whisperx-api" AND duration > 5s
```

Find failed requests:

```
service="whisperx-api" AND error=true
```

Find specific operations:

```
service="whisperx-api" AND operation="ml.transcribe"
```

### Metrics Queries (Prometheus)

Request rate:

```promql
sum(rate(audio_processing_requests_total[5m]))
```

P95 latency:

```promql
histogram_quantile(0.95, rate(audio_processing_duration_seconds_bucket[5m]))
```

Success rate:

```promql
sum(rate(audio_processing_requests_total{status="success"}[5m]))
  / sum(rate(audio_processing_requests_total[5m]))
```

Active tasks:

```promql
sum(active_tasks)
```

## Configuration Reference

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `observability__OTEL_ENABLED` | bool | true | Enable/disable observability |
| `observability__OTEL_SERVICE_NAME` | string | whisperx-api | Service name |
| `observability__OTEL_SERVICE_VERSION` | string | 0.4.1 | Service version |
| `observability__OTEL_EXPORTER_OTLP_ENDPOINT` | string | None | OTLP endpoint URL |
| `observability__OTEL_EXPORTER_OTLP_INSECURE` | bool | true | Use insecure connection |
| `observability__OTEL_TRACE_SAMPLE_RATE` | float | 1.0 | Sampling rate (0.0-1.0) |
| `observability__OTEL_METRICS_ENABLED` | bool | true | Enable metrics |
| `observability__OTEL_METRICS_PORT` | int | 9090 | Metrics endpoint port |
| `ENVIRONMENT` | string | production | Environment (affects sampling) |

### Sampling Rates

- **development**: 100% (all traces)
- **testing**: 100% (all traces)
- **production**: Configured rate (default 10%)

### Resource Attributes

Automatically included in all traces and metrics:

- `service.name`: Service identifier
- `service.version`: Application version
- `deployment.environment`: Environment name
- `host.name`: Hostname
- `gpu.available`: GPU availability
- `gpu.count`: Number of GPUs (if available)
- `gpu.device`: Configured device (cuda/cpu)

## Architecture

```
┌───────────────────────────────────────────────┐
│                                               │
│         WhisperX FastAPI Application          │
│                                               │
│  ┌─────────────────────────────────────────┐ │
│  │     OpenTelemetry Instrumentation       │ │
│  │                                         │ │
│  │  ┌───────────┐  ┌──────────┐  ┌──────┐│ │
│  │  │  Tracing  │  │ Metrics  │  │ Logs ││ │
│  │  └─────┬─────┘  └────┬─────┘  └───┬──┘│ │
│  └────────┼─────────────┼─────────────┼───┘ │
│           │             │             │     │
└───────────┼─────────────┼─────────────┼─────┘
            │             │             │
            ▼             ▼             │
       ┌────────┐   ┌──────────┐       │
       │ OTLP   │   │Prometheus│       │
       │Exporter│   │ Endpoint │       │
       └────┬───┘   └────┬─────┘       │
            │            │             │
            ▼            ▼             ▼
       ┌────────┐   ┌──────────┐  ┌──────┐
       │ Jaeger │   │Prometheus│  │ Logs │
       │        │   │  Server  │  │Parser│
       └────┬───┘   └────┬─────┘  └───┬──┘
            │            │             │
            └────────────┴─────────────┘
                         │
                         ▼
                   ┌──────────┐
                   │ Grafana  │
                   │Dashboard │
                   └──────────┘
```

## Best Practices

### Development

1. **Enable 100% sampling**: Set `ENVIRONMENT=development`
2. **Use metrics endpoint**: Monitor <http://localhost:9090/metrics>
3. **Test trace propagation**: Verify background task continuity
4. **Check span attributes**: Ensure meaningful data is captured

### Production

1. **Configure sampling**: Set appropriate `OTEL_TRACE_SAMPLE_RATE`
2. **Set up alerting**: Create Prometheus alert rules
3. **Monitor dashboards**: Use Grafana for visualization
4. **Correlate logs**: Use trace_id for troubleshooting
5. **Regular reviews**: Analyze slow traces and errors

### Performance

- **Minimal overhead**: <5% CPU, <50MB memory
- **Batch export**: Spans exported in batches
- **Async operations**: No blocking on export
- **Low cardinality**: Keep metric labels low cardinality

## Troubleshooting

### Traces not appearing

1. Check `OTEL_EXPORTER_OTLP_ENDPOINT` configuration
2. Verify Jaeger/collector is accessible
3. Check application logs for export errors
4. Verify sampling rate is appropriate

### Metrics not updating

1. Check <http://localhost:9090/metrics> endpoint
2. Verify `OTEL_METRICS_ENABLED=true`
3. Check Prometheus scrape configuration
4. Verify network connectivity

### High memory usage

1. Reduce trace sampling rate
2. Check for high-cardinality metric labels
3. Review Prometheus retention settings
4. Consider using recording rules

## Resources

- [Tracing Guide](./tracing.md) - Detailed tracing documentation
- [Metrics Guide](./metrics.md) - Comprehensive metrics reference
- [OpenTelemetry Docs](https://opentelemetry.io/docs/) - Official documentation
- [Prometheus Guide](https://prometheus.io/docs/) - Prometheus documentation
- [Jaeger Documentation](https://www.jaegertracing.io/docs/) - Jaeger tracing

## Support

For issues or questions:

1. Check the documentation in this directory
2. Review application logs for observability errors
3. Open an issue on GitHub with:
   - Configuration details
   - Error messages
   - Steps to reproduce
