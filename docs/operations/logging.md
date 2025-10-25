# Logging Configuration and Audit Trail

This document describes the consolidated logging configuration and audit trail system in whisperX-FastAPI.

## Overview

The application uses a consolidated, environment-aware logging system that provides:

- **Environment-specific configuration** (development, testing, production)
- **Structured JSON logging** for production environments
- **Human-readable colored output** for development
- **Comprehensive audit trail** for security and compliance
- **Single source of truth** for all logging configuration

## Architecture

### Directory Structure

```
app/core/logging/
├── __init__.py                 # Module exports and logger instance
├── audit_events.py             # Audit event types and dataclass
├── audit_logger.py             # Audit logging facade
├── base_config.py              # Base logging configuration
├── config_builder.py           # Dynamic configuration builder
├── dev_config.py               # Development environment config
├── formatters.py               # Custom log formatters
├── prod_config.py              # Production environment config
└── test_config.py              # Testing environment config
```

### Configuration Selection

The logging configuration is automatically selected based on the `ENVIRONMENT` variable:

- `ENVIRONMENT=development` → Human-readable colored output, DEBUG level
- `ENVIRONMENT=production` → JSON structured logging, INFO level, file handlers, audit logs
- `ENVIRONMENT=testing` → Minimal logging, WARNING level
- Default (unknown) → Production configuration

## Configuration Files

### Base Configuration (`base_config.py`)

Provides the foundation shared across all environments:

- Standard formatters (default, detailed)
- Console and error console handlers
- Logger hierarchy (app, whisperX, uvicorn, sqlalchemy, etc.)
- Default log levels

### Development Configuration (`dev_config.py`)

Optimized for local development:

```python
# Features:
- Colorized terminal output
- DEBUG level for app loggers
- Shows SQL queries (sqlalchemy.engine at INFO)
- Short timestamp format (HH:MM:SS)
```

**Example output:**

```
14:30:15 - app.services.task_management_service - INFO - Task created with UUID: abc-123
14:30:15 - audit - INFO - Audit: create on task/abc-123
```

### Production Configuration (`prod_config.py`)

Optimized for production deployments:

```python
# Features:
- JSON structured logging
- INFO level for app loggers
- File-based logging with rotation
- Separate audit log file
- 10MB log files, 5 backups for app.log
- 50MB log files, 10 backups for audit.log
```

**Example JSON output:**

```json
{
  "timestamp": "2025-10-25T14:30:15.123Z",
  "level": "INFO",
  "logger": "app.services.task_management_service",
  "message": "Task created with UUID: abc-123"
}
```

### Testing Configuration (`test_config.py`)

Minimizes noise during test execution:

```python
# Features:
- WARNING level for most loggers
- ERROR level for uvicorn and sqlalchemy
- No file handlers
- Minimal console output
```

## Environment Variables

### Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `production` | Environment name: development, testing, production |
| `LOG_LEVEL` | env-specific | Override log level: DEBUG, INFO, WARNING, ERROR |
| `LOGS_DIR` | `logs` | Directory for log files (production only) |

### Examples

```bash
# Development with debug logging
export ENVIRONMENT=development
export LOG_LEVEL=DEBUG

# Production with info logging
export ENVIRONMENT=production
export LOG_LEVEL=INFO

# Production with custom log directory
export ENVIRONMENT=production
export LOGS_DIR=/var/log/whisperx
```

## Audit Logging

### Overview

The audit logging system provides a comprehensive trail of security-relevant events for compliance and troubleshooting.

### Audit Event Types

```python
class AuditEventType(str, Enum):
    TASK_CREATED = "task.created"
    TASK_COMPLETED = "task.completed"
    TASK_DELETED = "task.deleted"
    FILE_UPLOADED = "file.uploaded"
    FILE_DOWNLOADED = "file.downloaded"
    FILE_DELETED = "file.deleted"
    AUTH_SUCCESS = "auth.success"           # Future
    AUTH_FAILURE = "auth.failure"           # Future
    CONFIG_CHANGED = "config.changed"       # Future
    ERROR_OCCURRED = "error.occurred"       # Future
```

### Audit Event Fields

Every audit event includes:

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | `AuditEventType` | Type of event |
| `resource_type` | `str` | Resource being accessed (e.g., "task", "file") |
| `resource_id` | `str` | Unique identifier for the resource |
| `action` | `str` | Action performed (e.g., "create", "delete") |
| `user_id` | `str` | User identifier (default: "anonymous") |
| `ip_address` | `str` | Client IP address (default: "unknown") |
| `request_id` | `str` | Request correlation ID (default: "unknown") |
| `timestamp` | `datetime` | Event timestamp (UTC, ISO 8601 format) |
| `details` | `dict` | Additional event-specific details |

### Using the Audit Logger

#### Basic Usage

```python
from app.core.logging.audit_logger import AuditLogger

# Log task creation
AuditLogger.log_task_created(
    task_id="task-123",
    task_type="transcription",
    user_id="user-456",
    ip_address="192.168.1.1",
    request_id="req-789"
)

# Log file upload
AuditLogger.log_file_uploaded(
    file_name="audio.mp3",
    file_size=1024000,
    content_type="audio/mpeg",
    user_id="user-456"
)
```

#### Service Integration Example

```python
from app.core.logging.audit_logger import AuditLogger

class TaskManagementService:
    def create_task(
        self,
        task: Task,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> str:
        """Create a new task with audit logging."""
        identifier = self.repository.add(task)

        # Audit log the creation
        AuditLogger.log_task_created(
            task_id=identifier,
            task_type=task.task_type,
            user_id=user_id,
            ip_address=ip_address,
            request_id=request_id,
        )

        return identifier
```

### Audit Log Output

#### Production (JSON Format)

```json
{
  "timestamp": "2025-10-25T14:30:00.123456Z",
  "level": "INFO",
  "logger": "audit",
  "message": "Audit: create on task/abc-123",
  "event_type": "task.created",
  "resource_type": "task",
  "resource_id": "abc-123",
  "action": "create",
  "user_id": "user-456",
  "ip_address": "192.168.1.1",
  "request_id": "req-789",
  "details": {
    "task_type": "transcription"
  }
}
```

#### Development (Human-Readable)

```
14:30:00 - audit - INFO - Audit: create on task/abc-123
```

## Log Files

### Production Log Files

When `ENVIRONMENT=production`, logs are written to files in the `LOGS_DIR` (default: `logs/`):

| File | Purpose | Max Size | Backups | Retention |
|------|---------|----------|---------|-----------|
| `app.log` | Application logs | 10 MB | 5 | ~50 MB total |
| `audit.log` | Audit trail | 50 MB | 10 | ~500 MB total |

### Log Rotation

- **Strategy**: Size-based rotation
- **Format**: `app.log`, `app.log.1`, `app.log.2`, etc.
- **Compression**: Not enabled by default (can be added via external tools)

### Retention Policy

- **Application logs**: 5 backups (~50 MB, approximately 1-7 days depending on volume)
- **Audit logs**: 10 backups (~500 MB, recommended minimum 90 days for compliance)

**For longer retention:**

- Use external log aggregation (ELK, Splunk, CloudWatch)
- Implement log archiving script
- Mount persistent volumes in Docker/Kubernetes

## Integration with Log Aggregation

### ELK Stack (Elasticsearch, Logstash, Kibana)

**Logstash configuration for JSON logs:**

```ruby
input {
  file {
    path => "/var/log/whisperx/app.log"
    codec => "json"
    type => "application"
  }
  file {
    path => "/var/log/whisperx/audit.log"
    codec => "json"
    type => "audit"
  }
}

filter {
  # Add custom fields or transformations
  if [type] == "audit" {
    mutate {
      add_field => { "[@metadata][index]" => "audit" }
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "%{[@metadata][index]-%{+YYYY.MM.dd}"
  }
}
```

### AWS CloudWatch

```python
# Use watchtower for CloudWatch integration
# Add to requirements: watchtower

from app.core.logging.prod_config import get_prod_config
import watchtower

config = get_prod_config()
config["handlers"]["cloudwatch"] = {
    "()": "watchtower.CloudWatchLogHandler",
    "log_group": "whisperx-api",
    "stream_name": "app-logs",
}
config["loggers"]["app"]["handlers"].append("cloudwatch")
```

### Google Cloud Logging

```python
# Use google-cloud-logging
# Add to requirements: google-cloud-logging

from google.cloud import logging as gcloud_logging

client = gcloud_logging.Client()
handler = client.get_default_handler()
config["handlers"]["google_cloud"] = {
    "()": "google.cloud.logging.handlers.CloudLoggingHandler",
    "client": client,
}
```

## Querying Logs

### Development (Text Logs)

```bash
# Tail application logs
tail -f logs/app.log

# Search for specific task
grep "task-123" logs/app.log

# Show errors only
grep '"level":"ERROR"' logs/app.log
```

### Production (JSON Logs)

#### Using `jq` for JSON parsing

```bash
# View formatted JSON logs
cat logs/app.log | jq '.'

# Filter by log level
cat logs/app.log | jq 'select(.level=="ERROR")'

# Find logs for specific task
cat logs/app.log | jq 'select(.message | contains("task-123"))'

# Extract audit events
cat logs/audit.log | jq 'select(.event_type=="task.created")'

# Get audit events for specific user
cat logs/audit.log | jq 'select(.user_id=="user-456")'

# Count events by type
cat logs/audit.log | jq -r '.event_type' | sort | uniq -c

# Extract events in time range
cat logs/audit.log | jq 'select(.timestamp > "2025-10-25T00:00:00" and .timestamp < "2025-10-26T00:00:00")'
```

#### Using Python for complex queries

```python
import json
from datetime import datetime

def query_audit_logs(
    event_type=None,
    user_id=None,
    start_time=None,
    end_time=None
):
    """Query audit logs with filters."""
    with open('logs/audit.log', 'r') as f:
        for line in f:
            log = json.loads(line)

            # Apply filters
            if event_type and log.get('event_type') != event_type:
                continue
            if user_id and log.get('user_id') != user_id:
                continue
            if start_time:
                log_time = datetime.fromisoformat(log['timestamp'])
                if log_time < start_time:
                    continue
            if end_time:
                log_time = datetime.fromisoformat(log['timestamp'])
                if log_time > end_time:
                    continue

            yield log

# Example usage
for event in query_audit_logs(
    event_type="task.created",
    user_id="user-456"
):
    print(f"{event['timestamp']}: {event['resource_id']}")
```

## Troubleshooting

### Common Issues

#### 1. Logs not appearing

**Symptom**: No log output or missing log files

**Solutions**:

```bash
# Check environment variable
echo $ENVIRONMENT

# Verify logs directory exists and is writable
ls -la logs/
mkdir -p logs/
chmod 755 logs/

# Check log level
echo $LOG_LEVEL

# Verify logging configuration
python -c "from app.core.logging import get_logging_config; import json; print(json.dumps(get_logging_config(), indent=2))"
```

#### 2. Permission denied errors

**Symptom**: `PermissionError: [Errno 13] Permission denied: 'logs/app.log'`

**Solutions**:

```bash
# Fix permissions
chmod 755 logs/
chmod 644 logs/*.log

# Or run with correct user
chown -R appuser:appgroup logs/
```

#### 3. Disk space issues

**Symptom**: Logs filling up disk space

**Solutions**:

```bash
# Check disk usage
du -sh logs/

# Clean old logs
find logs/ -name "*.log.*" -mtime +30 -delete

# Implement log rotation with logrotate
# Create /etc/logrotate.d/whisperx:
/path/to/whisperx/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

#### 4. JSON parsing errors

**Symptom**: Malformed JSON in log files

**Solutions**:

```bash
# Validate JSON logs
cat logs/app.log | jq empty

# Find malformed lines
awk '{print NR, $0}' logs/app.log | while read line; do
    echo "$line" | jq empty 2>/dev/null || echo "Error on line: $line"
done
```

## Best Practices

### 1. Log Levels

- **DEBUG**: Detailed information for diagnosing problems (dev only)
- **INFO**: Confirmation that things are working as expected
- **WARNING**: Something unexpected but the application can continue
- **ERROR**: Due to a serious problem, some function failed
- **CRITICAL**: System failure, application may not be able to continue

### 2. What to Log

**DO log:**

- Application startup/shutdown
- Configuration changes
- User actions (via audit log)
- External API calls (request/response)
- Database operations (in development)
- Background task execution
- Error conditions with stack traces

**DON'T log:**

- Sensitive data (passwords, tokens, PII)
- Excessive repetitive information
- Data that could fill disk quickly

### 3. Structured Logging

Use structured data in log messages:

```python
# Good
logger.info("Task completed", extra={
    "task_id": task_id,
    "duration": duration,
    "result_size": len(result)
})

# Avoid
logger.info(f"Task {task_id} completed in {duration}s with {len(result)} items")
```

### 4. Security Considerations

- **Never log credentials**: Passwords, API keys, tokens
- **Sanitize PII**: Redact or hash personal information
- **Secure log files**: Restrict access permissions (600 or 640)
- **Encrypt in transit**: Use TLS for log shipping
- **Audit log retention**: Keep audit logs for compliance period (90+ days)

## Summary

The consolidated logging system provides:

✅ Environment-specific configuration
✅ Structured JSON logging for production
✅ Human-readable output for development
✅ Comprehensive audit trail
✅ Easy integration with log aggregation services
✅ Flexible querying and analysis
✅ Backward compatibility with existing code

For questions or issues, refer to the code in `app/core/logging/` or create an issue in the repository.
