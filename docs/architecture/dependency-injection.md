# Dependency Injection Container

## Overview

The WhisperX FastAPI application uses a dependency injection container to manage service lifecycles and dependencies. This approach centralizes service creation, simplifies testing, and makes the dependency graph explicit.

## Container Structure

The application uses the `dependency-injector` library to implement the Dependency Injection pattern. The main container is defined in `app/core/container.py`.

### Container Class

```python
from dependency_injector import containers, providers
from app.core.container import Container

# Container manages all application dependencies
container = Container()
```

### Dependency Graph

```text
Container
├── Configuration (Settings)
│   └── Singleton - Application configuration
├── Database
│   ├── db_engine (Singleton) - Database engine
│   └── db_session_factory (Factory) - Session factory
├── Repositories
│   └── task_repository (Factory) - Task repository with session
├── Services
│   ├── file_service (Singleton) - Stateless file operations
│   └── task_management_service (Factory) - Task management with repository
└── ML Services (Singletons for model caching)
    ├── transcription_service - WhisperX transcription
    ├── diarization_service - Speaker diarization
    ├── alignment_service - Transcript alignment
    └── speaker_assignment_service - Speaker assignment
```

## Service Lifecycles

The container manages different lifecycle patterns for different types of services:

### Singleton

**Used for:** Stateless services and services with heavy initialization (ML models).

**Behavior:** Created once and reused across all requests.

**Examples:**

- `config` - Application settings
- `file_service` - Stateless file operations
- ML services - Models loaded once and cached

```python
file_service = providers.Singleton(FileService)
transcription_service = providers.Singleton(WhisperXTranscriptionService)
```

### Factory

**Used for:** Services that need per-request state or database sessions.

**Behavior:** New instance created for each request.

**Examples:**

- `task_repository` - Needs its own database session
- `task_management_service` - Depends on repository (which needs session)

```python
task_repository = providers.Factory(
    SQLAlchemyTaskRepository,
    session=db_session_factory,
)

task_management_service = providers.Factory(
    TaskManagementService,
    repository=task_repository,
)
```

## Using the Container

### In Application Startup

The container is initialized in `app/main.py` and made available to dependency providers:

```python
# app/main.py
from app.core.container import Container
from app.api import dependencies

# Create container
container = Container()

# Set container in dependencies module
dependencies.set_container(container)
```

### In API Endpoints

Services are injected into FastAPI endpoints using the `Depends()` mechanism:

```python
from fastapi import Depends
from app.api.dependencies import get_task_repository, get_file_service
from app.domain.repositories.task_repository import ITaskRepository
from app.services.file_service import FileService

@router.post("/tasks")
async def create_task(
    repository: ITaskRepository = Depends(get_task_repository),
    file_service: FileService = Depends(get_file_service),
):
    # Use injected dependencies
    task_id = repository.add(task)
    return {"id": task_id}
```

### Dependency Provider Functions

Provider functions in `app/api/dependencies.py` retrieve services from the container:

```python
def get_task_repository() -> Generator[ITaskRepository, None, None]:
    """Provide task repository from container."""
    if _container is None:
        raise RuntimeError("Container not initialized")
    yield _container.task_repository()

def get_file_service() -> Generator[FileService, None, None]:
    """Provide file service from container."""
    if _container is None:
        raise RuntimeError("Container not initialized")
    yield _container.file_service()
```

## Testing with Test Container

For testing, the application provides a `TestContainer` that overrides production services with mocks:

### Test Container Structure

```python
# tests/fixtures/test_container.py
from app.core.container import Container
from tests.mocks import MockTranscriptionService, MockDiarizationService

class TestContainer(Container):
    """Test container with mock implementations."""

    # Override ML services with fast mocks (no GPU, no network)
    transcription_service = providers.Singleton(MockTranscriptionService)
    diarization_service = providers.Singleton(MockDiarizationService, hf_token="mock")

    # Override database with in-memory SQLite
    db_engine = providers.Singleton(
        create_engine,
        "sqlite:///:memory:",
    )
```

### Using Test Container in Tests

```python
import pytest
from tests.fixtures import TestContainer

@pytest.fixture
def test_container():
    """Provide test container for testing."""
    container = TestContainer()
    yield container

def test_with_mocks(test_container):
    """Test using mock services from container."""
    # Get mock service from container
    transcription_service = test_container.transcription_service()

    # Use mock service - fast, deterministic, no GPU required
    result = transcription_service.transcribe(audio, params)
    assert result["text"] == "Mock transcription"
```

### Benefits of Test Container

1. **Fast Tests**: Mock services avoid slow GPU operations
2. **Deterministic**: Mocks return predictable results
3. **Isolated**: In-memory database prevents test interference
4. **Easy Setup**: Single container provides all mocks

## Adding New Dependencies

### Step 1: Register in Container

Add the new service to `app/core/container.py`:

```python
class Container(containers.DeclarativeContainer):
    # ... existing providers ...

    # New service
    my_new_service = providers.Factory(
        MyNewService,
        dependency1=some_dependency,
        dependency2=another_dependency,
    )
```

### Step 2: Create Dependency Provider

Add a provider function in `app/api/dependencies.py`:

```python
def get_my_new_service() -> Generator[MyNewService, None, None]:
    """Provide my new service from container."""
    if _container is None:
        raise RuntimeError("Container not initialized")
    yield _container.my_new_service()
```

### Step 3: Use in Endpoints

Inject the service into your endpoint:

```python
@router.post("/endpoint")
async def my_endpoint(
    my_service: MyNewService = Depends(get_my_new_service),
):
    # Use the service
    result = my_service.do_something()
    return result
```

### Step 4: Add Test Mock (Optional)

If testing requires mocks, override in `TestContainer`:

```python
class TestContainer(Container):
    # Override with mock implementation
    my_new_service = providers.Singleton(MockMyNewService)
```

## Choosing Lifecycle

### Use Singleton When

- Service has no state (stateless)
- Service has expensive initialization (ML models)
- Service can be safely shared across requests
- Examples: Config, FileService, ML services

### Use Factory When

- Service needs per-request state
- Service requires database sessions
- Service depends on other per-request services
- Examples: Repositories, TaskManagementService

## Benefits of Dependency Injection

1. **Centralized Management**: All dependencies defined in one place
2. **Easy Testing**: Swap implementations by overriding providers
3. **Explicit Dependencies**: Dependency graph is clear and documented
4. **Lifecycle Control**: Singletons vs factories managed automatically
5. **Reduced Boilerplate**: No manual factory functions needed
6. **Type Safety**: Full type hints maintained throughout

## Technical Implementation Notes

### Why Not Use @inject Decorator?

The `dependency-injector` library provides an `@inject` decorator with `Provide[]` markers, but this conflicts with FastAPI's dependency injection system. Instead, we use a manual approach:

1. Container is created at module level
2. Container reference is set in dependencies module via `set_container()`
3. Provider functions call container methods directly

This maintains FastAPI compatibility while leveraging dependency-injector's lifecycle management.

### Generator Pattern

All provider functions use the generator pattern (`yield`) to ensure compatibility with FastAPI's dependency system:

```python
def get_service() -> Generator[Service, None, None]:
    yield _container.service()
```

This allows FastAPI to properly manage the dependency lifecycle and cleanup.

## References

- [dependency-injector documentation](https://python-dependency-injector.ets-labs.org/)
- [FastAPI dependency injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Container class: `app/core/container.py`](../../app/core/container.py)
- [Dependency providers: `app/api/dependencies.py`](../../app/api/dependencies.py)
- [Test container: `tests/fixtures/test_container.py`](../../tests/fixtures/test_container.py)
