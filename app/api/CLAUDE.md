# app/api

HTTP layer: routers, schemas, mappers, dependency injection, and exception handlers.

## Routers

| File | Purpose |
| --- | --- |
| `audio_api.py` | Full pipeline (transcribe → align → diarize → combine) |
| `audio_services_api.py` | Individual service endpoints |
| `task_api.py` | Task CRUD and status polling |
| `callbacks.py` | Webhook callback delivery |

All routers are registered in `main.py` via `app.include_router()`.

## Schemas (`schemas/`)

Pydantic `BaseModel` for every request body and response. Always set `response_model` on
route decorators — this controls serialization and OpenAPI docs. Never return raw dicts
from endpoints.

## Dependencies (`dependencies.py`)

All services are injected via `Depends(get_*)`. The `_container` module-level variable is
set by `main.py` calling `dependencies.set_container(container)` during startup.

**Never import the Container directly inside a router.** Route handlers declare their
service dependencies as function parameters with `Depends(...)`.

## Mappers (`mappers/`)

Convert between API schemas and domain entities. Keep routers thin:

1. Call mapper to convert request schema → domain input
2. Call service method
3. Call mapper to convert domain result → response schema
4. Return response

No business logic in routers or mappers.

## Exception Handlers (`exception_handlers.py`)

| Exception | HTTP Status |
| --- | --- |
| `TaskNotFoundError` | 404 |
| `ValidationError` | 422 |
| `DomainError` | 400 |
| `InfrastructureError` | 503 |

Raise domain exceptions from services; never raise `HTTPException` inside a service.
Handlers attach `correlation_id` from the exception to the error response body.
