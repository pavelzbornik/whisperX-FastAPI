# app/core/CLAUDE.md

Config, DI Container, and exception hierarchy for the application.

## Settings (`config.py`)

`get_settings()` returns a cached `Settings` instance built with pydantic-settings.
Settings are grouped: `settings.whisper`, `settings.database`, `settings.logging`,
`settings.callback`. Load order: defaults → `.env` file → environment variables.

**Critical rule:** When `DEVICE=cpu`, `COMPUTE_TYPE` is automatically corrected to `int8`
inside the settings validator. Tests always run with `DEVICE=cpu` and `COMPUTE_TYPE=int8`.

Never instantiate `Settings()` directly — always call `get_settings()`.

## DI Container (`container.py`)

Uses `dependency-injector` `DeclarativeContainer`. Lifecycle:

- **Singletons** — ML services (models are expensive to load; reuse across requests)
- **Factories** — repository and task services (each request gets a fresh instance with its own session)

The container is instantiated once in `main.py` (inside the lifespan context manager) and
passed to `app.api.dependencies` via `dependencies.set_container(container)`. Routers never
import the Container directly — they use `Depends(get_*)` from `dependencies.py`.

## Exception Hierarchy (`exceptions.py`)

```text
ApplicationError
├── DomainError
│   ├── ValidationError
│   ├── TaskNotFoundError
│   └── (other domain-specific errors)
└── InfrastructureError
    ├── DatabaseOperationError
    └── ModelLoadError
```

Rules:

- Raise domain exceptions from services and repositories — never `HTTPException`.
- All exceptions carry a `correlation_id` for distributed tracing.
- `app/api/exception_handlers.py` maps exception types to HTTP status codes.
- Add new exception types here; register their handler in `exception_handlers.py`.
