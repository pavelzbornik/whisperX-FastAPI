# app/domain/CLAUDE.md

Pure Python domain layer — entities, repository interface, and ML service interfaces.

## Hard Rule: No Infrastructure Imports

Nothing in `app/domain/` may import from `app/infrastructure/`, SQLAlchemy, or any
third-party ML library. The domain layer must be importable with no heavy dependencies.

## Task Entity (`entities/task.py`)

`Task` is a plain Python dataclass with state-transition methods:

| Method | Guard (raises if violated) |
| --- | --- |
| `mark_as_processing()` | task must be pending |
| `mark_as_completed(result)` | task must be processing |
| `mark_as_failed(error)` | task must be processing |

Always check predicates before transitioning:
`is_pending()`, `is_processing()`, `is_completed()`, `is_failed()`.

Do not manipulate `status` directly — always go through the methods above.

## ITaskRepository (`repositories/`)

A `Protocol` defining the CRUD contract:
`get()`, `list()`, `create()`, `update()`, `delete()`.

The concrete implementation (`SQLAlchemyTaskRepository`) lives in `app/infrastructure/`.
Domain code only depends on the Protocol — this allows test mocks to satisfy the interface
without a real database.

## ML Service Interfaces (`services/`)

Four `Protocol` interfaces:

- `ITranscriptionService` — converts audio to a raw transcript
- `IAlignmentService` — word-level timestamp alignment
- `IDiarizationService` — speaker segmentation
- `ISpeakerAssignmentService` — assigns speakers to transcript segments

Implementations live in `app/infrastructure/ml/`. Tests use mocks from `tests/mocks/`.
