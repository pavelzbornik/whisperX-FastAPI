# Configuration Guide

This document describes the configuration options available for the whisperX FastAPI application.

## Environment Variables

### Basic Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `production` | Application environment (development, staging, production) |
| `LOG_LEVEL` | `INFO` (prod), `DEBUG` (dev) | Logging level |
| `DEFAULT_LANG` | `en` | Default language for transcription |
| `WHISPER_MODEL` | `tiny` | Default WhisperX model to use |
| `DEVICE` | `cuda` (if available), `cpu` | Processing device |
| `COMPUTE_TYPE` | `float16` (GPU), `int8` (CPU) | Computation precision |

### Database Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_URL` | `sqlite:///records.db` | Database connection URL |

### Security & Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_TOKEN` | None | Hugging Face API token (required for some models) |
| `ENABLE_CORS` | `false` | Enable CORS for cross-origin requests |

### File Upload Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_FILE_SIZE_MB` | `500` | Maximum file upload size in MB |

### Request Processing

| Variable | Default | Description |
|----------|---------|-------------|
| `REQUEST_TIMEOUT_SECONDS` | `3600` | Maximum request processing time |

## Health Check Endpoints

The application provides several health check endpoints for monitoring:

### `/health`
Simple health check that returns basic service status.

**Response:**
```json
{
  "status": "ok",
  "message": "Service is running",
  "correlation_id": "uuid",
  "timestamp": 1640995200.0
}
```

### `/health/live`
Liveness probe for container orchestration.

**Response:**
```json
{
  "status": "ok",
  "timestamp": 1640995200.0,
  "message": "Application is live",
  "correlation_id": "uuid",
  "uptime_seconds": 3600.5
}
```

### `/health/ready`
Comprehensive readiness check with detailed system metrics.

**Response:**
```json
{
  "status": "ok",
  "timestamp": 1640995200.0,
  "correlation_id": "uuid",
  "components": {
    "database": {
      "status": "healthy",
      "message": "Database connection successful"
    },
    "system_resources": {
      "status": "healthy",
      "message": "System resources within acceptable limits"
    }
  },
  "system_metrics": {
    "cpu_percent": 25.5,
    "cpu_count": 8,
    "memory": {
      "total_mb": 16384.0,
      "used_mb": 8192.0,
      "available_mb": 8192.0,
      "usage_percent": 50.0
    },
    "disk": {
      "total_gb": 1000.0,
      "used_gb": 500.0,
      "free_gb": 500.0,
      "usage_percent": 50.0
    }
  },
  "gpu_info": {
    "available": true,
    "devices": [
      {
        "device_id": 0,
        "name": "NVIDIA GeForce RTX 3080",
        "memory_used_mb": 2048.0,
        "memory_total_mb": 10240.0,
        "memory_free_mb": 8192.0,
        "memory_usage_percent": 20.0
      }
    ]
  }
}
```

## Request Tracing

All requests are automatically assigned a correlation ID for tracing. You can:

1. **View correlation IDs** in response headers (`X-Correlation-ID`)
2. **Provide custom correlation IDs** via request header (`X-Correlation-ID`)
3. **Track requests** through logs using the correlation ID

## File Upload Validation

The application validates uploaded files for:

- **File size limits** (configurable via `MAX_FILE_SIZE_MB`)
- **Supported file formats** (audio/video extensions)
- **File content validation** (basic magic number checks)
- **Empty file detection**

Supported formats:
- Audio: `.mp3`, `.wav`, `.aac`, `.ogg`, `.oga`, `.m4a`, `.wma`, `.amr`
- Video: `.mp4`, `.mov`, `.avi`, `.wmv`, `.mkv`

## Error Handling

The application provides detailed error responses with:

- **Specific error codes** (400, 413, 422, 500, 503)
- **Descriptive error messages**
- **Correlation IDs** for error tracking
- **Request timing information**

## Monitoring Integration

The enhanced health checks are designed to work with monitoring systems like:

- **Kubernetes** (liveness/readiness probes)
- **Docker Swarm** (health checks)
- **Load balancers** (health endpoints)
- **Monitoring tools** (Prometheus, Grafana compatible)

## Production Deployment

For production deployments, consider:

1. **Set appropriate file size limits** based on your infrastructure
2. **Configure request timeouts** for your use case
3. **Set up proper secrets management** for `HF_TOKEN`
4. **Monitor health check endpoints**
5. **Configure log aggregation** to track correlation IDs
6. **Set resource limits** based on health check warnings