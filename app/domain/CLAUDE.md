# app/domain

Pure Python domain layer — entities, repository interface, and ML service interfaces.

## Hard Rule: No Infrastructure Imports

Nothing in `app/domain/` may import from `app/infrastructure/`, SQLAlchemy, or any
third-party ML library. The domain layer must be importable with no heavy dependencies.

## Task Entity (`entities/task.py`)

`Task` is a plain Python dataclass with state-transition methods:

| Method | Description |
| --- | --- |
| `mark_as_queued()` | Set status to queued (accepted, waiting to be processed) |
| `mark_as_processing()` | Set status to processing (task execution started) |
| `mark_as_completed(result)` | Set status to completed with result data |
| `mark_as_failed(error)` | Set status to failed with error message |

Lifecycle: `queued` → `processing` → `completed` / `failed`

Always check predicates before transitioning:
`is_queued()`, `is_processing()`, `is_completed()`, `is_failed()`.

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
