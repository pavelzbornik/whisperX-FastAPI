# Exception Handling Architecture

## Overview

This document describes the custom exception hierarchy implemented for domain-driven error handling in the whisperX-FastAPI application. The exception system provides clear separation of concerns, consistent error responses, and proper HTTP status code mapping.

## Design Principles

1. **Domain-Driven**: Exceptions represent business concepts, not HTTP concerns
2. **Separation of Concerns**: Domain layer never imports FastAPI/HTTP concepts
3. **Consistent Responses**: All errors follow a standard JSON format
4. **Request Tracing**: Correlation IDs enable tracking errors across logs
5. **User-Friendly**: Separate internal messages from user-facing messages

## Exception Hierarchy

```text
ApplicationError (base)
├── DomainError (business logic violations)
│   ├── ValidationError (input validation)
│   │   ├── InvalidAudioFormatError
│   │   ├── AudioTooLargeError
│   │   ├── AudioTooShortError
│   │   ├── UnsupportedFileExtensionError
│   │   └── FileValidationError
│   ├── TaskNotFoundError
│   ├── TaskAlreadyCompletedError
│   ├── TaskAlreadyFailedError
│   ├── InvalidTaskStateError
│   ├── TranscriptionFailedError
│   ├── DiarizationFailedError
│   ├── AlignmentFailedError
│   └── AudioProcessingError
├── InfrastructureError (external system failures)
│   ├── ModelLoadError
│   ├── InsufficientMemoryError
│   ├── FileDownloadError
│   └── DatabaseError
└── ConfigurationError (application config issues)
    └── MissingConfigurationError
```

## Base Exception Class

All custom exceptions inherit from `ApplicationError`:

```python
class ApplicationError(Exception):
    """Base exception for all application errors.

    Attributes:
        message: Human-readable error message for developers/logs
        code: Machine-readable error code for API responses
        correlation_id: Unique ID for request tracing across logs
        user_message: Safe message to show end users
        details: Additional error context as keyword arguments
    """

    def __init__(
        self,
        message: str,
        code: str = "APPLICATION_ERROR",
        correlation_id: Optional[str] = None,
        user_message: Optional[str] = None,
        **details: Any,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.user_message = user_message or message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dict for JSON response."""
        return {
            "error": {
                "message": self.user_message,
                "code": self.code,
                "correlation_id": self.correlation_id,
                **self.details,
            }
        }
```

## Exception Categories

### DomainError

Raised when business rules are violated or domain operations cannot be completed.

- **HTTP Status**: 400 Bad Request (or specific codes for subclasses)
- **Examples**: `TaskAlreadyCompletedError`, `TranscriptionFailedError`
- **Use When**: Business logic prevents an operation

### ValidationError

Raised when user input fails validation rules.

- **HTTP Status**: 422 Unprocessable Entity
- **Examples**: `InvalidAudioFormatError`, `AudioTooLargeError`
- **Use When**: Input validation fails

### InfrastructureError

Raised when external dependencies fail.

- **HTTP Status**: 503 Service Unavailable
- **Examples**: `ModelLoadError`, `FileDownloadError`
- **Use When**: Database, file system, external API, or ML model fails

### TaskNotFoundError

Special case of DomainError for missing resources.

- **HTTP Status**: 404 Not Found
- **Use When**: A requested resource doesn't exist

## Exception Handlers

Exception handlers are registered in `app/main.py` and map exceptions to HTTP responses:

```python
# Register exception handlers (order matters!)
app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
app.add_exception_handler(ValidationError, validation_error_handler)
app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(InfrastructureError, infrastructure_error_handler)
app.add_exception_handler(Exception, generic_error_handler)
```

### Handler Behavior

| Handler | Status Code | User Message | Internal Details Exposed |
|---------|-------------|--------------|-------------------------|
| `task_not_found_handler` | 404 | User-friendly | No |
| `validation_error_handler` | 422 | Validation details | Yes (safe) |
| `domain_error_handler` | 400 | User-friendly | No |
| `infrastructure_error_handler` | 503 | Generic message | **No** (security) |
| `generic_error_handler` | 500 | Generic message | **No** (security) |

## Error Response Format

All errors follow this consistent JSON structure:

```json
{
  "error": {
    "message": "User-friendly error message",
    "code": "ERROR_CODE",
    "correlation_id": "uuid-for-tracing",
    "field": "optional-field-name",
    "additional_context": "..."
  }
}
```

## Usage Examples

### Raising Domain Exceptions in Services

**Before (BAD - Leaky Abstraction):**

```python
from fastapi import HTTPException

def get_task(self, identifier: str):
    task = self.repository.get_by_id(identifier)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

**After (GOOD - Domain Exception):**

```python
from app.core.exceptions import TaskNotFoundError

def get_task(self, identifier: str):
    task = self.repository.get_by_id(identifier)
    if not task:
        raise TaskNotFoundError(identifier)
    return task
```

### Handling External Errors

**Wrapping ML Model Errors:**

```python
from app.core.exceptions import TranscriptionFailedError

try:
    result = whisperx_model.transcribe(audio)
except Exception as e:
    raise TranscriptionFailedError(
        reason="Model failed to process audio",
        original_error=e
    )
```

### Validation in API Layer

**File Upload Validation:**

```python
from app.core.exceptions import FileValidationError

if file.filename is None:
    raise FileValidationError(
        filename="unknown",
        reason="Filename is missing"
    )
```

## Correlation IDs

Correlation IDs enable tracing errors across the system:

1. **Automatic Generation**: Each exception gets a UUID if not provided
2. **Logging**: All handlers log with correlation_id
3. **Response**: Correlation ID returned to client
4. **Support**: Users can provide correlation ID when reporting issues

### Future Enhancement: Correlation ID Middleware

```python
# To be implemented in Task 17
class CorrelationIDMiddleware:
    async def __call__(self, request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        # Add to request state
        request.state.correlation_id = correlation_id
        # Pass to exceptions
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
```

## When to Use Each Exception Type

### Use TaskNotFoundError when

- Looking up a task by ID that doesn't exist
- Attempting to access a non-existent resource

### Use ValidationError (or subclasses) when

- File extension not supported
- File too large or too small
- Invalid JSON format
- Missing required fields
- Invalid parameter values

### Use DomainError (or subclasses) when

- Business rule violated (e.g., can't modify completed task)
- Processing failed (transcription, diarization, alignment)
- Invalid state transition

### Use InfrastructureError (or subclasses) when

- Database connection failed
- ML model failed to load
- Out of memory
- File download failed
- External API unavailable

### Use ConfigurationError when

- Required environment variable missing
- Invalid configuration value
- Configuration file corrupt

## Adding New Exceptions

To add a new exception:

1. **Define the exception class** in `app/core/exceptions.py`:

```python
class NewDomainError(DomainError):
    """Description of when this error occurs."""

    def __init__(self, param: str, correlation_id: Optional[str] = None) -> None:
        super().__init__(
            message=f"Detailed message for logs: {param}",
            code="NEW_ERROR_CODE",
            user_message="User-friendly message",
            correlation_id=correlation_id,
            param=param,
        )
```

2. **Add tests** in `tests/unit/core/test_exceptions.py`:

```python
def test_new_domain_error() -> None:
    exc = NewDomainError(param="test")
    assert isinstance(exc, DomainError)
    assert exc.code == "NEW_ERROR_CODE"
    assert "test" in exc.message
```

3. **Use in services** (not in API layer):

```python
if some_condition:
    raise NewDomainError(param=value)
```

4. **(Optional) Add specific handler** if needed:

```python
async def new_error_handler(request, exc):
    # Custom handling
    pass

app.add_exception_handler(NewDomainError, new_error_handler)
```

## Testing Exception Handlers

Test that handlers return correct status codes and format:

```python
def test_new_error_returns_correct_status():
    response = client.get("/endpoint-that-raises-error")

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NEW_ERROR_CODE"
    assert "correlation_id" in data["error"]
```

## Migration Checklist

When converting existing code to use the new exception system:

- [ ] Replace `HTTPException` imports with domain exception imports
- [ ] Replace `raise HTTPException(...)` with appropriate domain exception
- [ ] Update tests to expect domain exceptions instead of HTTPException
- [ ] Verify error messages are user-friendly
- [ ] Ensure no sensitive data in user messages
- [ ] Add correlation_id to logs
- [ ] Remove try/catch blocks that were only for HTTPException translation

## Security Considerations

1. **Never expose internal details** in user messages for InfrastructureError
2. **Sanitize database errors** before showing to users
3. **Log full stack traces** but only return safe messages
4. **Validate all user input** before processing
5. **Use correlation IDs** for support, not debugging information in responses

## Best Practices

1. **Raise early**: Validate at the entry point (API layer)
2. **Handle late**: Let exception handlers deal with HTTP mapping
3. **Be specific**: Use the most specific exception type available
4. **Add context**: Include relevant details in exception kwargs
5. **Log appropriately**: INFO for user errors, ERROR for system errors
6. **Test exhaustively**: Cover all error paths in tests
7. **Document clearly**: Explain when to use each exception type

## References

- Exception classes: `app/core/exceptions.py`
- Exception handlers: `app/api/exception_handlers.py`
- Handler registration: `app/main.py`
- Exception tests: `tests/unit/core/test_exceptions.py`
- Handler tests: `tests/unit/api/test_exception_handlers.py`
