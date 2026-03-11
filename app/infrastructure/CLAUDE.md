# app/infrastructure

Database and ML infrastructure — concrete implementations of domain interfaces.

## Database Layer

### ORM Models (`database/models.py`)

SQLAlchemy ORM models only. No business logic, no state-transition methods. Column names
may differ from domain entity fields — mappers handle the translation.

### Mappers (`database/mappers/task_mapper.py`)

Two functions — always use them, never read ORM fields directly in services:

- `to_domain(orm_task) -> Task` — converts `TaskORM` → `Task` domain entity
- `to_orm(domain_task) -> TaskORM` — converts `Task` → `TaskORM` for persistence

### Repository (`database/repositories/sqlalchemy_task_repository.py`)

Concrete `ITaskRepository` implementation. Owns session usage, exception wrapping
(re-raises as `DatabaseOperationError`), and logging. Background tasks call
`SessionLocal()` directly and pass the session to the repository constructor;
request-scoped code receives the repository via DI (Container factory).

### Unit of Work (`database/unit_of_work.py`)

Use `SQLAlchemyUnitOfWork` as a context manager for atomic multi-step operations:

```python
with SQLAlchemyUnitOfWork(session) as uow:
    uow.tasks.create(task)
    uow.commit()   # explicit commit required — no auto-commit
```

If an exception is raised inside the block, the UoW rolls back automatically.

## ML Layer (`ml/`)

WhisperX implementations of the four domain service Protocols
(`ITranscriptionService`, `IAlignmentService`, `IDiarizationService`,
`ISpeakerAssignmentService`). Registered as **Singletons** in the DI Container so
models are loaded once at startup and reused across requests.

Use `# type: ignore` freely for whisperx and torch APIs — they lack complete type stubs.
