# OpenTelemetry Tracing Guide

## Overview

WhisperX FastAPI is instrumented with OpenTelemetry to provide distributed tracing across all layers of the application. This enables you to track requests from the API endpoint through background task processing to ML inference.

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP Request
       ▼
┌─────────────────────────────────────────┐
│      FastAPI Application                │
│  ┌────────────────────────────────┐    │
│  │  FastAPIInstrumentor (auto)    │    │
│  └────────────────────────────────┘    │
│         │                               │
│         ▼                               │
│  ┌────────────────────────────────┐    │
│  │  SQLAlchemyInstrumentor (auto) │    │
│  └────────────────────────────────┘    │
│         │                               │
│         ▼                               │
│  ┌────────────────────────────────┐    │
│  │  Custom Spans                  │    │
│  │  - audio.validate_and_save     │    │
│  │  - audio.load_and_validate     │    │
│  │  - audio_processing.*          │    │
│  │  - ml.transcribe               │    │
│  └────────────────────────────────┘    │
└─────────────────────────────────────────┘
         │ Traces
         ▼
    ┌────────┐
    │ OTLP   │
    │Exporter│
    └────┬───┘
         │
         ▼
    ┌────────┐
    │ Jaeger │
    │ Zipkin │
    │ or     │
    │ Other  │
    └────────┘
```

## Configuration

### Environment Variables

Configure tracing via environment variables or `.env` file:

```bash
# Enable/disable observability
observability__OTEL_ENABLED=true

# Service identification
observability__OTEL_SERVICE_NAME=whisperx-api
observability__OTEL_SERVICE_VERSION=0.4.1

# OTLP exporter endpoint (if not set, traces are generated but not exported)
observability__OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Use insecure connection (for dev/test)
observability__OTEL_EXPORTER_OTLP_INSECURE=true

# Sampling rate (0.0-1.0, overridden by environment-based defaults)
observability__OTEL_TRACE_SAMPLE_RATE=0.1  # 10% in production

# Environment affects sampling: development=100%, production=configured rate
ENVIRONMENT=development
```

### Sampling Strategy

The application uses environment-based sampling:

- **Development**: 100% sampling (all traces captured)
- **Testing**: 100% sampling
- **Production**: Configurable rate (default 10%)

Sampling uses `ParentBasedTraceIdRatio` which:

- Respects parent span sampling decisions (maintains trace continuity)
- Samples new traces based on trace ID (consistent sampling)

## Trace Structure

### HTTP Request Span Hierarchy

```
HTTP POST /speech-to-text
├── audio.validate_and_save
│   └── [file validation and save operations]
├── audio.load_and_validate
│   └── [audio processing and duration calculation]
└── audio_processing.transcription (background)
    ├── ml.transcribe
    │   ├── model_loading_started (event)
    │   ├── model_loaded (event)
    │   ├── transcription_started (event)
    │   └── transcription_completed (event)
    ├── ml.align
    ├── ml.diarize
    └── ml.assign_speakers
```

### Key Spans

#### 1. HTTP Request Spans (Automatic)

Automatically created by FastAPIInstrumentor:

**Span Name**: `GET /endpoint` or `POST /endpoint`

**Attributes**:

- `http.method`: HTTP method (GET, POST, etc.)
- `http.url`: Full request URL
- `http.status_code`: Response status code
- `http.route`: FastAPI route pattern

#### 2. Database Query Spans (Automatic)

Automatically created by SQLAlchemyInstrumentor:

**Span Name**: `SELECT` / `INSERT` / `UPDATE` / `DELETE`

**Attributes**:

- `db.statement`: SQL query (with trace context in comments)
- `db.system`: Database system (sqlite, postgresql, etc.)

#### 3. Audio Processing Spans (Custom)

**audio.validate_and_save**

Validates file extension and saves upload.

**Attributes**:

- `file.name`: Original filename
- `file.size_bytes`: File size in bytes
- `file.path`: Temporary file path

**Events**:

- `file_uploaded`: When file is successfully saved

**audio.load_and_validate**

Loads audio and calculates duration.

**Attributes**:

- `audio.duration_seconds`: Audio duration
- `audio.filename`: Original filename

**audio_processing.{task_type}**

Parent span for entire background task processing.

**Attributes**:

- `task.id`: Task UUID
- `task.type`: Type of task (transcription, diarization, etc.)
- `task.duration_seconds`: Total processing time
- `task.status`: Final status (completed/failed)
- `error.type`: Exception type if failed

**Events**:

- `task_started`: When background processing begins
- `task_completed`: When processing finishes successfully

#### 4. ML Operation Spans (Custom)

**ml.transcribe**

Transcription using WhisperX model.

**Attributes**:

- `ml.model`: Model name (tiny, base, small, etc.)
- `ml.language`: Language code
- `ml.device`: Device type (cuda/cpu)
- `ml.compute_type`: Computation type (float16, int8)
- `ml.batch_size`: Batch size
- `ml.task`: Task type (transcribe/translate)
- `ml.model_load_duration_seconds`: Time to load model
- `ml.inference_duration_seconds`: Inference time
- `ml.total_duration_seconds`: Total time including cleanup
- `ml.segments_count`: Number of segments produced
- `gpu.memory_before_mb`: GPU memory before (if CUDA)
- `gpu.memory_after_mb`: GPU memory after processing

**Events**:

- `model_loading_started`: Model download/load begins
- `model_loaded`: Model ready for inference
- `transcription_started`: Inference begins
- `transcription_completed`: Inference complete

## Querying Traces

### Jaeger Queries

#### Find Slow Requests

```
service="whisperx-api" AND duration > 5s
```

#### Find Failed Requests

```
service="whisperx-api" AND error=true
```

#### Find Transcription Operations

```
service="whisperx-api" AND operation="ml.transcribe"
```

#### Find Large Audio Files

```
service="whisperx-api" AND file.size_bytes > 10485760
```

#### Find GPU Operations

```
service="whisperx-api" AND ml.device="cuda"
```

### Trace Context in Logs

All application logs include trace context when a span is active:

```
2025-10-25 18:04:45,172 [INFO] trace_id=a1b2c3d4e5f6... span_id=1234567890ab... app.api.audio_api: Received file upload request
```

You can correlate logs with traces using the `trace_id`.

## Best Practices

### 1. Always Propagate Context to Background Tasks

When spawning background tasks, capture and pass trace context:

```python
from opentelemetry import context

# In endpoint
trace_context = context.get_current()
background_tasks.add_task(my_task, params, trace_context)

# In background task
from opentelemetry import context

def my_task(params, trace_context=None):
    token = None
    if trace_context is not None:
        token = context.attach(trace_context)

    try:
        # Your work here
        pass
    finally:
        if token is not None:
            context.detach(token)
```

### 2. Add Meaningful Span Attributes

Record relevant information as span attributes:

```python
span.set_attributes({
    "audio.duration": duration,
    "file.size": file_size,
    "model.name": model_name,
})
```

### 3. Use Span Events for Key Milestones

Add events to mark important points in processing:

```python
span.add_event("model_loaded", {
    "model_name": model,
    "load_duration": duration,
})
```

### 4. Record Exceptions

Always record exceptions in spans:

```python
try:
    result = do_work()
except Exception as e:
    span.record_exception(e)
    span.set_status(Status(StatusCode.ERROR, str(e)))
    raise
```

### 5. Set Span Status

Explicitly set span status for clarity:

```python
from opentelemetry.trace import Status, StatusCode

# On success
span.set_status(Status(StatusCode.OK))

# On error
span.set_status(Status(StatusCode.ERROR, "Error message"))
```

## Troubleshooting

### Traces Not Appearing

1. **Check OTLP endpoint**: Verify `OTEL_EXPORTER_OTLP_ENDPOINT` is correctly set
2. **Check sampling**: Development should sample 100%, verify environment
3. **Check exporter logs**: Look for connection errors in application logs
4. **Verify collector is running**: Test connectivity to OTLP endpoint

### Broken Trace Continuity

1. **Verify context propagation**: Ensure background tasks receive trace context
2. **Check for async boundaries**: Context may be lost across async operations
3. **Review token attach/detach**: Ensure proper cleanup of context tokens

### High Cardinality Attributes

Avoid high-cardinality attributes that can overwhelm backends:

❌ **Bad**: `user.id`, `file.path` (unique per request)
✅ **Good**: `task.type`, `ml.model`, `http.status_code` (finite set)

## Performance Impact

OpenTelemetry adds minimal overhead:

- **Sampling**: Reduces export volume in production
- **Batch export**: Spans exported in batches, not per-span
- **Async export**: Export happens asynchronously, doesn't block requests
- **No export mode**: Can run with tracing but no export for testing

Expected overhead: <5% CPU, <50MB memory
