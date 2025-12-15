# OpenTelemetry Metrics Guide

## Overview

WhisperX FastAPI exposes Prometheus-compatible metrics that provide insights into application performance, resource usage, and business operations.

## Architecture

```
┌─────────────────────────────────────────┐
│      FastAPI Application                │
│  ┌────────────────────────────────┐    │
│  │  Metrics Collection            │    │
│  │  - Request counters            │    │
│  │  - Duration histograms         │    │
│  │  - Active task gauges          │    │
│  └────────────────────────────────┘    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
            ┌──────────┐
            │Prometheus│
            │ Exporter │
            └─────┬────┘
                  │ /metrics endpoint
                  │ (port 9090)
                  ▼
            ┌──────────┐
            │Prometheus│
            │  Server  │
            └─────┬────┘
                  │
                  ▼
            ┌──────────┐
            │ Grafana  │
            │Dashboard │
            └──────────┘
```

## Configuration

### Environment Variables

```bash
# Enable/disable metrics
observability__OTEL_ENABLED=true
observability__OTEL_METRICS_ENABLED=true

# Metrics endpoint port
observability__OTEL_METRICS_PORT=9090
```

### Accessing Metrics

Metrics are exposed at:

```
http://localhost:9090/metrics
```

Format: Prometheus text exposition format

## Available Metrics

### Audio Processing Metrics

#### audio_processing_requests_total

**Type**: Counter
**Unit**: requests
**Description**: Total number of audio processing requests

**Labels**:

- `status`: Request outcome (success, error)
- `task_type`: Type of processing (transcription, diarization, etc.)
- `error_type`: Exception type (if status=error)

**Example Queries**:

```promql
# Total requests
sum(audio_processing_requests_total)

# Request rate (per second)
rate(audio_processing_requests_total[5m])

# Success rate
sum(rate(audio_processing_requests_total{status="success"}[5m]))
  / sum(rate(audio_processing_requests_total[5m]))

# Error rate by type
sum by (error_type) (rate(audio_processing_requests_total{status="error"}[5m]))
```

#### audio_processing_duration_seconds

**Type**: Histogram
**Unit**: seconds
**Description**: Audio processing duration distribution

**Labels**:

- `task_type`: Type of processing

**Buckets**: Auto-configured by Prometheus exporter

**Example Queries**:

```promql
# P50 (median) latency
histogram_quantile(0.5,
  rate(audio_processing_duration_seconds_bucket[5m]))

# P95 latency
histogram_quantile(0.95,
  rate(audio_processing_duration_seconds_bucket[5m]))

# P99 latency
histogram_quantile(0.99,
  rate(audio_processing_duration_seconds_bucket[5m]))

# Average duration
rate(audio_processing_duration_seconds_sum[5m])
  / rate(audio_processing_duration_seconds_count[5m])

# Duration by task type
histogram_quantile(0.95,
  sum by (task_type, le) (rate(audio_processing_duration_seconds_bucket[5m])))
```

#### audio_file_size_bytes

**Type**: Histogram
**Unit**: bytes
**Description**: Distribution of uploaded audio file sizes

**Example Queries**:

```promql
# Average file size
rate(audio_file_size_bytes_sum[5m])
  / rate(audio_file_size_bytes_count[5m])

# P95 file size
histogram_quantile(0.95, rate(audio_file_size_bytes_bucket[5m]))

# Files over 10MB
sum(rate(audio_file_size_bytes_bucket{le="10485760"}[5m]))
```

#### audio_duration_seconds

**Type**: Histogram
**Unit**: seconds
**Description**: Distribution of audio durations

**Example Queries**:

```promql
# Average audio duration
rate(audio_duration_seconds_sum[5m])
  / rate(audio_duration_seconds_count[5m])

# P95 audio duration
histogram_quantile(0.95, rate(audio_duration_seconds_bucket[5m]))

# Processing time vs audio duration ratio
(rate(audio_processing_duration_seconds_sum[5m]) / rate(audio_processing_duration_seconds_count[5m]))
  / (rate(audio_duration_seconds_sum[5m]) / rate(audio_duration_seconds_count[5m]))
```

### ML Operation Metrics

#### ml_model_loads_total

**Type**: Counter
**Unit**: loads
**Description**: Total number of ML model loads

**Labels**:

- `model_name`: Model identifier (tiny, base, small, etc.)

**Example Queries**:

```promql
# Total model loads
sum(ml_model_loads_total)

# Model load rate
rate(ml_model_loads_total[5m])

# Most frequently loaded models
topk(5, sum by (model_name) (rate(ml_model_loads_total[1h])))
```

#### ml_inference_duration_seconds

**Type**: Histogram
**Unit**: seconds
**Description**: ML inference operation duration

**Labels**:

- `operation`: ML operation type (transcribe, align, diarize)
- `model`: Model name

**Example Queries**:

```promql
# P95 inference duration
histogram_quantile(0.95,
  rate(ml_inference_duration_seconds_bucket[5m]))

# Average inference time by operation
rate(ml_inference_duration_seconds_sum[5m])
  / rate(ml_inference_duration_seconds_count[5m])

# Transcription inference time
histogram_quantile(0.95,
  rate(ml_inference_duration_seconds_bucket{operation="transcribe"}[5m]))

# Inference time by model
histogram_quantile(0.95,
  sum by (model, le) (rate(ml_inference_duration_seconds_bucket[5m])))
```

### Task Management Metrics

#### active_tasks

**Type**: UpDownCounter (Gauge-like)
**Unit**: tasks
**Description**: Number of currently active tasks

**Labels**:

- `status`: Task status (processing)
- `task_type`: Type of task

**Example Queries**:

```promql
# Current active tasks
sum(active_tasks)

# Active tasks by type
sum by (task_type) (active_tasks)

# Task queue depth over time
sum(active_tasks{status="processing"})
```

## Prometheus Configuration

### Scrape Configuration

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'whisperx-api'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: '/metrics'
```

### Recording Rules

Create useful aggregations:

```yaml
groups:
  - name: whisperx_rules
    interval: 30s
    rules:
      # Request rate
      - record: whisperx:request_rate:5m
        expr: |
          sum(rate(audio_processing_requests_total[5m]))

      # Success rate
      - record: whisperx:success_rate:5m
        expr: |
          sum(rate(audio_processing_requests_total{status="success"}[5m]))
            / sum(rate(audio_processing_requests_total[5m]))

      # P95 latency
      - record: whisperx:latency:p95:5m
        expr: |
          histogram_quantile(0.95,
            rate(audio_processing_duration_seconds_bucket[5m]))

      # Active task count
      - record: whisperx:active_tasks:current
        expr: |
          sum(active_tasks)
```

### Alerting Rules

Example alert rules:

```yaml
groups:
  - name: whisperx_alerts
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          sum(rate(audio_processing_requests_total{status="error"}[5m]))
            / sum(rate(audio_processing_requests_total[5m]))
            > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }} over 5 minutes"

      # High P95 latency
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            rate(audio_processing_duration_seconds_bucket[5m]))
            > 300
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High P95 latency detected"
          description: "P95 latency is {{ $value }}s"

      # Many active tasks (potential bottleneck)
      - alert: HighTaskQueue
        expr: |
          sum(active_tasks) > 50
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "High number of active tasks"
          description: "{{ $value }} tasks are currently active"

      # No recent requests (potential downtime)
      - alert: NoRecentRequests
        expr: |
          sum(rate(audio_processing_requests_total[5m])) == 0
        for: 10m
        labels:
          severity: info
        annotations:
          summary: "No requests in the last 10 minutes"
          description: "Service may be down or not receiving traffic"
```

## Grafana Dashboard

### Example Dashboard JSON

Create a comprehensive dashboard with these panels:

#### 1. Request Rate Panel

```json
{
  "title": "Request Rate",
  "targets": [
    {
      "expr": "sum(rate(audio_processing_requests_total[5m]))",
      "legendFormat": "Total"
    },
    {
      "expr": "sum by (status) (rate(audio_processing_requests_total[5m]))",
      "legendFormat": "{{ status }}"
    }
  ],
  "type": "graph"
}
```

#### 2. Latency Percentiles Panel

```json
{
  "title": "Processing Latency",
  "targets": [
    {
      "expr": "histogram_quantile(0.50, rate(audio_processing_duration_seconds_bucket[5m]))",
      "legendFormat": "P50"
    },
    {
      "expr": "histogram_quantile(0.95, rate(audio_processing_duration_seconds_bucket[5m]))",
      "legendFormat": "P95"
    },
    {
      "expr": "histogram_quantile(0.99, rate(audio_processing_duration_seconds_bucket[5m]))",
      "legendFormat": "P99"
    }
  ],
  "type": "graph"
}
```

#### 3. Success Rate Panel

```json
{
  "title": "Success Rate",
  "targets": [
    {
      "expr": "sum(rate(audio_processing_requests_total{status=\"success\"}[5m])) / sum(rate(audio_processing_requests_total[5m]))",
      "legendFormat": "Success Rate"
    }
  ],
  "type": "graph",
  "format": "percentunit"
}
```

#### 4. Active Tasks Panel

```json
{
  "title": "Active Tasks",
  "targets": [
    {
      "expr": "sum(active_tasks)",
      "legendFormat": "Total Active"
    },
    {
      "expr": "sum by (task_type) (active_tasks)",
      "legendFormat": "{{ task_type }}"
    }
  ],
  "type": "graph"
}
```

#### 5. ML Model Performance Panel

```json
{
  "title": "ML Inference Duration by Operation",
  "targets": [
    {
      "expr": "histogram_quantile(0.95, sum by (operation, le) (rate(ml_inference_duration_seconds_bucket[5m])))",
      "legendFormat": "{{ operation }} (P95)"
    }
  ],
  "type": "graph"
}
```

### Complete Dashboard Template

See [grafana-dashboard.json](./grafana-dashboard.json) for a complete dashboard configuration.

## Best Practices

### 1. Use Appropriate Metric Types

- **Counter**: For values that only increase (requests, errors)
- **Histogram**: For distributions (latencies, sizes)
- **Gauge**: For values that go up and down (active tasks, memory)

### 2. Keep Cardinality Low

Avoid high-cardinality labels:

❌ **Bad**: `user_id`, `task_id`, `file_path`
✅ **Good**: `task_type`, `status`, `model_name`

### 3. Use Consistent Naming

Follow Prometheus naming conventions:

- Suffix with unit: `_seconds`, `_bytes`, `_total`
- Use underscores, not hyphens
- Start with namespace: `whisperx_`

### 4. Set Reasonable Scrape Intervals

- **High-traffic**: 15-30s
- **Low-traffic**: 60s
- **Very low-traffic**: 5m

### 5. Use Recording Rules

Pre-compute expensive queries with recording rules to improve dashboard performance.

## Troubleshooting

### Metrics Not Appearing

1. **Check endpoint**: Verify <http://localhost:9090/metrics> is accessible
2. **Check configuration**: Verify `OTEL_METRICS_ENABLED=true`
3. **Check Prometheus config**: Ensure scrape job is configured
4. **Check firewall**: Ensure port 9090 is accessible

### Missing Labels

1. **Verify label recording**: Check metric definition in code
2. **Check PromQL syntax**: Ensure `by` clause includes all labels
3. **Verify data exists**: Query without labels first

### High Memory Usage

1. **Reduce cardinality**: Remove high-cardinality labels
2. **Adjust retention**: Reduce Prometheus retention period
3. **Use recording rules**: Pre-aggregate data

## Performance Impact

Metrics collection adds minimal overhead:

- **Collection**: <1ms per metric update
- **Export**: Scraped by Prometheus (pull-based), no push overhead
- **Memory**: ~10-50MB for metric storage

Expected overhead: <2% CPU, <50MB memory
