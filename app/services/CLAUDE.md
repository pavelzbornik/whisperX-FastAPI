# app/services

Business logic orchestration — these services sit between the API layer and
infrastructure/domain layers.

## Service Responsibilities

| File | Responsibility |
| --- | --- |
| `audio_processing_service.py` | Entry point for background task execution |
| `whisperx_wrapper_service.py` | Coordinates the full WhisperX pipeline |
| `task_management_service.py` | Task CRUD via `ITaskRepository` |
| `file_service.py` | `UploadFile` saving and URL downloads to temp files |

## Session Lifecycle Rule

**Request-scoped services** (called from FastAPI route handlers) receive the repository
via DI — the Container factory handles session creation and cleanup.

**Background tasks** (`audio_processing_service.py`) run outside the request context and
must manage sessions directly:

```python
session = SyncSessionLocal()
try:
    repo = SyncSQLAlchemyTaskRepository(session)
    # ... do work ...
    session.commit()
finally:
    session.close()   # always close, even on error
```

Never rely on garbage collection to close a session.

## Pipeline Flow (`whisperx_wrapper_service.py`)

Calls domain ML service interfaces in order:

1. `ITranscriptionService.transcribe()` — raw transcript
2. `IAlignmentService.align()` — word timestamps
3. `IDiarizationService.diarize()` — speaker segments
4. `ISpeakerAssignmentService.assign()` — merge speakers into transcript

Each step is optional depending on the request parameters. The wrapper handles
step-skipping logic; individual ML services do not know about each other.
