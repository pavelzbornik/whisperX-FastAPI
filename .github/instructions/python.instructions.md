---
description: 'Python and FastAPI coding conventions and guidelines'
applyTo: '**/*.py'
---

# Python & FastAPI Coding Conventions

## Python General Guidelines

- Write clear and concise comments for each function.
- Ensure functions have descriptive names and include type hints.
- Provide docstrings following PEP 257 conventions.
- Use the `typing` module for type annotations (e.g., `List[str]`, `Dict[str, int]`, `Optional[str]`).
- Break down complex functions into smaller, more manageable functions.
- Always prioritize readability and clarity.
- Handle edge cases and write clear exception handling.
- Use consistent naming conventions and follow language-specific best practices.

## FastAPI Best Practices

### Router and Endpoint Organization

- **Organize routes by feature**: Group related endpoints in separate router files (see `app/routers/`).
- **Use dependency injection**: Leverage FastAPI's dependency injection for database sessions, authentication, configuration.
- **Tag endpoints**: Use tags for OpenAPI documentation organization (see `tags_metadata` in `app/main.py`).
- **Include endpoint summaries**: Add `summary` parameter to `@router.get/post/etc` for clear API docs.

### Request/Response Models

- **Use Pydantic schemas**: Define all request/response models in `app/schemas.py` using Pydantic `BaseModel`.
- **Validate inputs**: Leverage Pydantic's validation features (e.g., `Field`, `validator`, `root_validator`).
- **Use explicit response models**: Always specify `response_model` parameter in route decorators.
- **Avoid returning ORM models directly**: Convert SQLAlchemy models to Pydantic schemas before returning.

### Error Handling

- **Use HTTPException**: Raise `fastapi.HTTPException` with appropriate status codes.
- **Provide detailed error messages**: Include helpful context in exception detail field.
- **Use standard status codes**: Import from `fastapi.status` module (e.g., `status.HTTP_404_NOT_FOUND`).

Example:

```python
from fastapi import HTTPException, status

if not task:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Task not found"
    )
```

### Background Tasks

- **Use BackgroundTasks**: For long-running operations (transcription, alignment, diarization).
- **Store task state in database**: Use SQLAlchemy models to track task status (see `app/models.py`).
- **Return task identifier**: Allow clients to poll for results via task endpoints.

Example pattern (see `app/tasks.py`):

```python
from fastapi import BackgroundTasks

@router.post("/process")
async def process(background_tasks: BackgroundTasks):
    task_id = create_task_record()
    background_tasks.add_task(process_audio, task_id)
    return {"identifier": task_id, "message": "Task queued"}
```

### File Uploads

- **Use UploadFile**: For multipart file uploads (see `app/routers/stt.py`).
- **Validate file types**: Check extensions against allowed lists (see `app/config.py`).
- **Handle temporary files**: Clean up temp files after processing.

Example:

```python
from fastapi import UploadFile, File

@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    if not is_valid_extension(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type")
    # Process file
```

### Database Sessions

- **Use dependency injection for sessions**: Define session dependency in `app/db.py`.
- **Use context managers**: Ensure proper session cleanup.
- **Avoid session leaks**: Close sessions in finally blocks or use `try/finally`.

Example pattern:

```python
from sqlalchemy.orm import Session
from fastapi import Depends

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/items")
def get_items(db: Session = Depends(get_db)):
    return db.query(Item).all()
```

### Environment Configuration

- **Use Config class**: Centralize environment variables in `app/config.py`.
- **Load .env early**: Use `python-dotenv` to load environment before app initialization.
- **Provide defaults**: Set sensible defaults for optional config values.
- **Validate critical vars**: Ensure required vars (like `HF_TOKEN`) are set.

### Health Checks and Monitoring

- **Implement health endpoints**: Provide `/health`, `/health/live`, `/health/ready` (see `app/main.py`).
- **Check dependencies**: Readiness endpoint should verify database connectivity.
- **Use appropriate status codes**: Return 503 for unavailable dependencies.

### Logging

- **Use structured logging**: Configure logging in `app/logger.py`.
- **Log at appropriate levels**: DEBUG for development, INFO for production.
- **Include context**: Add request IDs, task IDs to log messages.
- **Use separate configs**: Different logging for Uvicorn vs Gunicorn.

### API Documentation

- **Customize OpenAPI**: Use `lifespan` context manager to generate and save OpenAPI specs.
- **Provide descriptions**: Add detailed descriptions to API operation decorators.
- **Document examples**: Include example requests/responses in Pydantic models.
- **Auto-redirect root**: Redirect `/` to `/docs` for convenience.

## Type Checking with mypy

### mypy Requirements

**Type checking is strictly enforced via mypy with these settings:**

- `disallow_untyped_defs = true`: All functions require complete type annotations
- `disallow_incomplete_defs = true`: Type annotations must be complete (no partial typing)
- `check_untyped_defs = true`: Code without types is still validated
- `warn_return_any = true`: Warns when functions return type `Any`
- `strict_equality = true`: Enforces strict equality checks

**Run mypy locally:**

```bash
uv run mypy app/  # Must show "Success: no issues found"
```

### Type Annotation Standards

**Required for all functions:**

- Parameter types on every argument
- Return type annotation (including `None` if applicable)
- Use Python 3.10+ syntax: `dict[str, Any]`, `list[str]`, `str | None`

**Example of correct typing:**

```python
from typing import Any
from collections.abc import Callable

def calculate_total(
    items: list[float],
    multiplier: int = 1,
    callback: Callable[[float], None] | None = None
) -> float:
    """Calculate total of items with optional callback.

    Args:
        items: List of numeric values
        multiplier: Multiplier for total (default 1)
        callback: Optional function to call with each item

    Returns:
        Total of items multiplied by multiplier
    """
    total: float = sum(items) * multiplier
    if callback is not None:
        for item in items:
            callback(item)
    return total
```

### Common mypy Errors and Fixes

#### Error: "Function is missing a type annotation"

```python
# ❌ Missing return type
def get_name(user_id: int):
    return "John"

# ✅ With return type
def get_name(user_id: int) -> str:
    return "John"
```

#### Error: "Argument of type X cannot be assigned to parameter of type Y"

```python
# ❌ Type mismatch
def process(value: str) -> None:
    pass

process(123)  # Error: int is not str

# ✅ Correct type
process("123")
```

#### Error: "Incompatible return value type"

```python
# ❌ Returns None sometimes
def get_first(items: list[str]) -> str:
    if items:
        return items[0]
    # Missing return - implicitly returns None

# ✅ Correct return type
def get_first(items: list[str]) -> str | None:
    if items:
        return items[0]
    return None
```

#### Error: "Object is possibly None"

```python
# ❌ UploadFile.filename is optional
file: UploadFile = ...
name = file.filename.upper()  # Error: filename could be None

# ✅ Check for None first
if file.filename is None:
    raise HTTPException(status_code=400, detail="Filename required")
name = file.filename.upper()  # Now safe
```

#### Error: "Cannot access attribute for unknown type"

```python
# ❌ Result from library with incomplete types
result = whisperx.load_model("tiny")  # Type is unknown (Any)
model_type = result.type_name  # Error: unknown attribute

# ✅ Use # type: ignore comment
result = whisperx.load_model("tiny")  # type: ignore[attr-defined]
model_type = result.type_name
```

### Handling Third-Party Library Types

**For libraries with incomplete type stubs:**

1. First, try to find type stubs (packages like `types-*`, `*-stubs`)
2. If unavailable, add `# type: ignore` comments

**Example with whisperx:**

```python
import whisperx  # Incomplete type information
from typing import Any

# Load model - library has incomplete types
model = whisperx.load_model("tiny", device="cpu")  # type: ignore[attr-defined]

# Explicit typing for better clarity
model: Any = whisperx.load_model("tiny", device="cpu")  # type: ignore

# Function that uses library
def transcribe_audio(audio_path: str) -> dict[str, Any]:
    """Transcribe audio using WhisperX."""
    audio = whisperx.load_audio(audio_path)  # type: ignore[attr-defined]
    result: dict[str, Any] = model.transcribe(audio)  # type: ignore[attr-defined]
    return result
```

## Code Style and Formatting

- Follow **PEP 8** style guide (enforced by Ruff).
- Use **Ruff** for linting and formatting (not flake8/black/isort).
- Maintain proper indentation (4 spaces).
- Place docstrings immediately after `def` or `class` keyword.
- Use blank lines to separate logical sections.
- **Use type annotations on all functions** (enforced by mypy).

## Testing Best Practices

- Use **TestClient** from `fastapi.testclient` for integration tests.
- Test all HTTP status codes (success, 4xx, 5xx).
- Mock external dependencies (ML models, external APIs).
- Use in-memory database for tests (`sqlite:///:memory:`).
- Test error conditions and edge cases.
- Achieve minimum 80% code coverage.

Example test structure:

```python
from fastapi.testclient import TestClient

def test_endpoint_success():
    response = client.post("/endpoint", json={"data": "value"})
    assert response.status_code == 200
    assert "expected_key" in response.json()

def test_endpoint_validation_error():
    response = client.post("/endpoint", json={})
    assert response.status_code == 422  # Validation error
```

## Type Hints and Complete Type Annotations

**All functions MUST have complete type annotations.** This is enforced by mypy with strict settings.

### Type Annotation Requirements

- **Function parameters**: Each parameter must have a type hint
- **Return values**: All functions must have return type annotations
- **Generic types**: Use modern syntax (Python 3.10+):
  - `dict[str, Any]` instead of `Dict[str, Any]`
  - `list[str]` instead of `List[str]`
  - `str | None` instead of `Optional[str]`
  - `set[str]` instead of `Set[str]`

### mypy Type Checking

The project uses mypy with strict settings to enforce type safety:

- Configured in `pyproject.toml` with `disallow_untyped_defs = true`
- Integrated into pre-commit hooks (runs on all Python files)
- Validated in CI pipeline on every PR

**Run mypy locally:**

```bash
uv run mypy app/  # Must show: Success: no issues found
```

### Type Annotations for Common Patterns

**Function with parameters and return type:**

```python
from typing import Any

def process_data(items: list[str], timeout: int = 30) -> dict[str, Any]:
    """Process items and return results.

    Args:
        items: List of items to process
        timeout: Timeout in seconds (default 30)

    Returns:
        Dictionary containing results
    """
    result: dict[str, Any] = {"status": "success", "count": len(items)}
    return result
```

**Async endpoint with type hints:**

```python
from typing import Any
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse

@router.post("/process", status_code=status.HTTP_200_OK)
async def process_file(file: UploadFile = File(...)) -> JSONResponse:
    """Process uploaded file.

    Args:
        file: Uploaded file to process

    Returns:
        JSON response with results

    Raises:
        HTTPException: If file validation fails
    """
    if file.filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing"
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"filename": file.filename, "size": file.size}
    )
```

**Optional and union types:**

```python
from typing import Any

def fetch_data(
    query: str,
    limit: int | None = None,
    format: str = "json"
) -> dict[str, Any] | None:
    """Fetch data with optional limit.

    Args:
        query: Search query
        limit: Optional result limit
        format: Output format (default: json)

    Returns:
        Results dictionary or None if not found
    """
    if not query:
        return None
    return {"query": query, "results": []}
```

**Callable types:**

```python
from collections.abc import Callable
from typing import Any

def execute_task(
    processor: Callable[[str], Any],
    data: str
) -> Any:
    """Execute a processing task.

    Args:
        processor: Callable that processes the data
        data: Input data to process

    Returns:
        Processing result
    """
    return processor(data)
```

**Generator/Iterator types:**

```python
from collections.abc import Generator
from sqlalchemy.orm import Session

def get_db_session() -> Generator[Session, None, None]:
    """Provide a transactional database session.

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**FastAPI endpoint with complete typing:**

```python
from typing import Any
from fastapi import APIRouter, HTTPException, status, UploadFile, File
from pydantic import BaseModel

class TaskResponse(BaseModel):
    """Response model for task creation."""
    identifier: str
    message: str
    status: str

@router.post(
    "/transcribe",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    tags=["Speech-2-Text"],
    summary="Transcribe audio file"
)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str | None = None,
    model: str | None = None
) -> TaskResponse:
    """
    Transcribe an audio or video file to text using WhisperX.

    Args:
        file: Audio/video file to transcribe
        language: Optional language code (default: en)
        model: Optional model size (default: from config)

    Returns:
        TaskResponse with task identifier and status

    Raises:
        HTTPException: If file type is invalid or processing fails
    """
    if file.filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required"
        )

    if not is_valid_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {ALLOWED_EXTENSIONS}"
        )

    # Implementation
    return TaskResponse(
        identifier=task_id,
        message="Task queued",
        status="pending"
    )
```
