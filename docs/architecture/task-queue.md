# Task Queue Architecture

## Overview

The task queue abstraction layer provides a clean separation between business logic and background task processing infrastructure. This enables future migration from FastAPI's built-in BackgroundTasks to distributed task queues (Celery, RQ, etc.) without changing application code.

## Architecture

### Design Pattern: Repository Pattern at Service Level

The task queue follows the Repository Pattern, providing a consistent interface (`ITaskQueue`) that abstracts the underlying task processing implementation.

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer                               │
│  (FastAPI Endpoints with BackgroundTasks dependency)        │
└──────────────────┬──────────────────────────────────────────┘
                   │ Depends(get_task_queue)
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                   Domain Layer                               │
│  ┌──────────────────────────────────────────────────┐       │
│  │  ITaskQueue Protocol (Interface)                 │       │
│  │  - enqueue(task_type, parameters, ...)          │       │
│  │  - get_status(task_id)                          │       │
│  │  - cancel(task_id)                              │       │
│  └──────────────────────────────────────────────────┘       │
│  ┌──────────────────────────────────────────────────┐       │
│  │  BackgroundTask Entity                           │       │
│  │  - Serializable task definition                 │       │
│  │  - Status tracking                               │       │
│  └──────────────────────────────────────────────────┘       │
└──────────────────┬──────────────────────────────────────────┘
                   │ implements
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              Infrastructure Layer                            │
│  ┌──────────────────────────────────────────────────┐       │
│  │  FastAPITaskQueue                                │       │
│  │  - Wraps FastAPI BackgroundTasks                │       │
│  │  - Persists tasks to database                   │       │
│  │  - Delegates execution to TaskExecutor          │       │
│  └─────────────────┬────────────────────────────────┘       │
│                    │ uses                                    │
│                    ▼                                         │
│  ┌──────────────────────────────────────────────────┐       │
│  │  TaskExecutor                                    │       │
│  │  - Executes tasks with retry logic              │       │
│  │  - Updates task status                          │       │
│  │  - Implements exponential backoff               │       │
│  └─────────────────┬────────────────────────────────┘       │
│                    │ uses                                    │
│                    ▼                                         │
│  ┌──────────────────────────────────────────────────┐       │
│  │  TaskRegistry                                    │       │
│  │  - Maps task types to handlers                  │       │
│  │  - Strategy pattern for handler selection       │       │
│  └──────────────────────────────────────────────────┘       │
│  ┌──────────────────────────────────────────────────┐       │
│  │  Audio Processing Handlers                      │       │
│  │  - transcription_handler                        │       │
│  │  - diarization_handler                          │       │
│  │  - alignment_handler                            │       │
│  │  - speaker_assignment_handler                   │       │
│  └──────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. ITaskQueue Protocol (Domain Layer)

**Location:** `app/domain/services/task_queue.py`

The protocol defines the contract for task queue implementations:

```python
class ITaskQueue(Protocol):
    def enqueue(
        self,
        task_type: str,
        parameters: dict[str, Any],
        task_id: str | None = None,
        max_retries: int = 3,
    ) -> str:
        """Enqueue a task for execution."""
        ...

    def get_status(self, task_id: str) -> TaskResult | None:
        """Get current status of a task."""
        ...

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        ...
```

**Benefits:**

- Swappable implementations (FastAPI → Celery → RQ)
- Testable via mocks
- Type-safe with Protocol typing

### 2. BackgroundTask Entity (Domain Layer)

**Location:** `app/domain/entities/background_task.py`

Pure domain object representing a task:

```python
@dataclass
class BackgroundTask:
    task_id: str
    task_type: str
    parameters: dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    error_message: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def serialize(self) -> str:
        """Serialize to JSON for storage."""
        ...

    @classmethod
    def deserialize(cls, json_str: str) -> "BackgroundTask":
        """Deserialize from JSON."""
        ...
```

**Features:**

- JSON serialization for persistence
- Immutable task definition
- Status lifecycle tracking

### 3. TaskRegistry (Infrastructure Layer)

**Location:** `app/infrastructure/tasks/task_registry.py`

Maps task types to handler functions:

```python
class TaskRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(self, task_type: str, handler: Callable[..., Any]) -> None:
        """Register a task handler."""
        ...

    def get_handler(self, task_type: str) -> Callable[..., Any] | None:
        """Get handler for task type."""
        ...
```

**Usage:**

```python
# During startup (in main.py lifespan)
registry = container.task_registry()
audio_handlers = container.audio_handlers()

for task_type, handler in audio_handlers.items():
    registry.register(task_type, handler)
```

### 4. TaskExecutor (Infrastructure Layer)

**Location:** `app/infrastructure/tasks/task_executor.py`

Executes tasks with retry logic:

```python
class TaskExecutor:
    def __init__(
        self,
        task_registry: TaskRegistry,
        task_repository: ITaskRepository
    ) -> None:
        ...

    def execute(self, task: BackgroundTask) -> Any:
        """Execute task with retry logic."""
        # 1. Update status to PROCESSING
        # 2. Check if cancelled
        # 3. Get handler from registry
        # 4. Execute handler
        # 5. Update status (COMPLETED/FAILED)
        # 6. Implement retry on failure
        ...
```

**Retry Strategy:**

- Exponential backoff: 2^n seconds (2, 4, 8)
- Configurable max retries (default: 3)
- Permanent failure after max retries

### 5. FastAPITaskQueue (Infrastructure Layer)

**Location:** `app/infrastructure/tasks/fastapi_task_queue.py`

Implementation wrapping FastAPI BackgroundTasks:

```python
class FastAPITaskQueue:
    def __init__(
        self,
        background_tasks: BackgroundTasks,
        task_executor: TaskExecutor,
        task_repository: ITaskRepository,
    ) -> None:
        ...

    def enqueue(
        self,
        task_type: str,
        parameters: dict[str, Any],
        task_id: str | None = None,
        max_retries: int = 3,
    ) -> str:
        """Enqueue task using FastAPI BackgroundTasks."""
        # 1. Create BackgroundTask entity
        # 2. Persist to database
        # 3. Schedule with FastAPI
        ...
```

**Limitations:**

- No true distributed processing
- Limited retry capabilities (no delayed retry)
- Tasks lost if application crashes
- Cannot cancel running tasks (only mark for cancellation)

## Task Lifecycle

```
PENDING → QUEUED → PROCESSING → COMPLETED
                              ↓ (on failure)
                            FAILED
                              ↓ (if retries remain)
                            QUEUED → PROCESSING → ...
                              ↓ (max retries exceeded)
                            FAILED (permanent)

Manual cancellation:
PENDING/QUEUED → CANCELLED
```

### Status Flow

1. **PENDING**: Task created but not yet enqueued
2. **QUEUED**: Task enqueued, waiting for execution
3. **PROCESSING**: Task currently executing
4. **COMPLETED**: Task finished successfully
5. **FAILED**: Task failed (permanently after max retries)
6. **CANCELLED**: Task cancelled by user

## Database Schema

New fields added to `tasks` table:

```sql
ALTER TABLE tasks ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE tasks ADD COLUMN max_retries INTEGER DEFAULT 3;
ALTER TABLE tasks ADD COLUMN last_error VARCHAR(500);
ALTER TABLE tasks ADD COLUMN scheduled_at DATETIME;
```

**Migration:**

```bash
python -m app.infrastructure.database.migrations.001_add_task_queue_fields
```

## Dependency Injection

### Container Configuration

**Location:** `app/core/container.py`

```python
class Container(containers.DeclarativeContainer):
    # Task registry - Singleton
    task_registry = providers.Singleton(TaskRegistry)

    # Task executor - Factory
    task_executor = providers.Factory(
        TaskExecutor,
        task_registry=task_registry,
        task_repository=task_repository,
    )

    # Audio handlers - Factory
    audio_handlers = providers.Factory(
        create_audio_processing_handler,
        transcription_service=transcription_service,
        diarization_service=diarization_service,
        alignment_service=alignment_service,
        speaker_service=speaker_assignment_service,
    )
```

### Dependency Provider

**Location:** `app/api/dependencies.py`

```python
def get_task_queue(
    background_tasks: BackgroundTasks,
) -> Generator[FastAPITaskQueue, None, None]:
    """Provide task queue for dependency injection."""
    task_executor = _container.task_executor()
    task_repository = _container.task_repository()

    yield FastAPITaskQueue(
        background_tasks=background_tasks,
        task_executor=task_executor,
        task_repository=task_repository,
    )
```

## Usage Examples

### Enqueuing a Task

```python
from fastapi import BackgroundTasks, Depends
from app.api.dependencies import get_task_queue
from app.infrastructure.tasks.fastapi_task_queue import FastAPITaskQueue

@router.post("/transcribe")
async def transcribe_audio(
    background_tasks: BackgroundTasks,
    task_queue: FastAPITaskQueue = Depends(get_task_queue),
) -> dict[str, str]:
    """Transcribe audio file."""
    task_id = task_queue.enqueue(
        task_type="transcription",
        parameters={
            "audio": audio_data,
            "language": "en",
            "model": "base",
            # ... other parameters
        },
        max_retries=3
    )

    return {"task_id": task_id, "status": "queued"}
```

### Checking Task Status

```python
@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    background_tasks: BackgroundTasks,
    task_queue: FastAPITaskQueue = Depends(get_task_queue),
) -> dict[str, Any]:
    """Get task status."""
    result = task_queue.get_status(task_id)

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": result.task_id,
        "status": result.status.value,
        "result": result.result,
        "error": result.error,
        "retry_count": result.retry_count,
        "duration": result.duration_seconds,
    }
```

### Cancelling a Task

```python
@router.delete("/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    task_queue: FastAPITaskQueue = Depends(get_task_queue),
) -> dict[str, str]:
    """Cancel a pending task."""
    success = task_queue.cancel(task_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Task cannot be cancelled (not found or already completed)"
        )

    return {"task_id": task_id, "status": "cancelled"}
```

### Creating Custom Task Handlers

```python
# 1. Define handler function
def my_custom_handler(param1: str, param2: int) -> dict[str, Any]:
    """Process custom task."""
    result = do_processing(param1, param2)
    return {"output": result}

# 2. Register during startup
task_registry = container.task_registry()
task_registry.register("custom_task", my_custom_handler)

# 3. Enqueue task
task_queue.enqueue(
    task_type="custom_task",
    parameters={"param1": "value", "param2": 42}
)
```

## Migration Path to Celery

When ready to scale to distributed processing:

### 1. Create Celery Implementation

**Location:** `app/infrastructure/tasks/celery_task_queue.py`

```python
from celery import Celery
from app.domain.services.task_queue import ITaskQueue

app = Celery('whisperx', broker='redis://localhost:6379/0')

class CeleryTaskQueue:
    """Celery implementation of ITaskQueue."""

    def enqueue(
        self,
        task_type: str,
        parameters: dict[str, Any],
        task_id: str | None = None,
        max_retries: int = 3,
    ) -> str:
        """Enqueue task using Celery."""
        # Create Celery task
        task = self._get_celery_task(task_type)
        result = task.apply_async(
            kwargs=parameters,
            task_id=task_id,
            max_retries=max_retries,
            retry_backoff=True,
        )
        return result.id

    def get_status(self, task_id: str) -> TaskResult | None:
        """Get status from Celery result backend."""
        result = AsyncResult(task_id, app=app)
        return TaskResult(
            task_id=task_id,
            status=TaskStatus(result.status.lower()),
            result=result.result,
            error=str(result.info) if result.failed() else None,
        )

    def cancel(self, task_id: str) -> bool:
        """Revoke Celery task."""
        app.control.revoke(task_id, terminate=True)
        return True
```

### 2. Update DI Container

```python
# app/core/container.py
class Container(containers.DeclarativeContainer):
    # Add configuration for task queue backend
    task_queue_backend = providers.Singleton(
        lambda: os.getenv("TASK_QUEUE_BACKEND", "fastapi")
    )

    # Conditional provider
    task_queue_impl = providers.Selector(
        task_queue_backend,
        fastapi=providers.Factory(FastAPITaskQueue, ...),
        celery=providers.Factory(CeleryTaskQueue, ...),
    )
```

### 3. Configure Environment

```bash
# .env
TASK_QUEUE_BACKEND=celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

### 4. No Application Code Changes

All existing code using `ITaskQueue` continues to work without modification.

## Testing

### Unit Tests

**Task Registry:**

```bash
pytest tests/unit/infrastructure/tasks/test_task_registry.py
```

**Task Executor:**

```bash
pytest tests/unit/infrastructure/tasks/test_task_executor.py
```

**Background Task Entity:**

```bash
pytest tests/unit/domain/entities/test_background_task.py
```

### Mocking for Tests

```python
from unittest.mock import Mock
from app.domain.services.task_queue import ITaskQueue

def test_service_with_mock_queue():
    """Test service using mock task queue."""
    mock_queue = Mock(spec=ITaskQueue)
    mock_queue.enqueue.return_value = "test-task-id"

    # Use mock in service
    service = MyService(task_queue=mock_queue)
    result = service.process_data(data)

    # Verify interaction
    mock_queue.enqueue.assert_called_once()
```

## Monitoring & Observability

### Task Metrics

Track key metrics:

- Queue depth (pending tasks)
- Processing time per task type
- Retry rate
- Failure rate
- Cancellation rate

### Logging

All components log at appropriate levels:

```python
# TaskExecutor
logger.info(f"Starting execution of task {task.task_id}")
logger.error(f"Task {task.task_id} failed: {error}", exc_info=True)

# TaskRegistry
logger.info(f"Registered handler for task type: {task_type}")
logger.warning(f"No handler registered for task type: {task_type}")
```

### Health Checks

Check task queue health:

```python
@router.get("/health/task-queue")
async def task_queue_health(
    task_registry: TaskRegistry = Depends(get_task_registry),
) -> dict[str, Any]:
    """Check task queue health."""
    return {
        "status": "healthy",
        "registered_task_types": task_registry.list_task_types(),
        "task_count": len(task_registry.list_task_types()),
    }
```

## Troubleshooting

### Task Stuck in PROCESSING

**Cause:** Application crashed during execution.

**Solution:**

1. Implement task timeout
2. Use heartbeat mechanism
3. Add task cleanup on startup

### High Retry Rate

**Cause:** Transient failures or resource issues.

**Solution:**

1. Review error logs
2. Adjust retry strategy
3. Increase max retries for specific tasks
4. Add exponential backoff with jitter

### Memory Leaks

**Cause:** Large result data stored in database.

**Solution:**

1. Store results in external storage (S3, MinIO)
2. Store only references in database
3. Implement result TTL and cleanup

## Best Practices

1. **Keep Handlers Stateless:** Handlers should be pure functions without side effects beyond their return value.

2. **Validate Parameters Early:** Validate task parameters before enqueueing to catch errors quickly.

3. **Use Explicit Task Types:** Use constants or enums for task types to avoid typos.

4. **Monitor Task Duration:** Set appropriate timeouts to prevent hanging tasks.

5. **Clean Up Resources:** Ensure handlers clean up any resources (files, connections) in finally blocks.

6. **Test with Mocks:** Use mock task queues in tests to avoid executing actual background tasks.

7. **Log Extensively:** Log at all lifecycle points for debugging and monitoring.

## References

- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- [Dependency Injection in Python](https://python-dependency-injector.ets-labs.org/)
