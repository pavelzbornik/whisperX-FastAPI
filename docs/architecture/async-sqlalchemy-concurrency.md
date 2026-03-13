# Async SQLAlchemy Migration — Concurrency Resilience

## Problem

Load testing revealed the server broke at ~20 concurrent users:

```text
QueuePool limit of size 15 overflow 30 reached, connection timed out, timeout 60.00
```

Two root causes:

1. **Sync DB calls blocked the event loop.** Route handlers were `async def` but
   called `session.query(...)` directly. Uvicorn is single-threaded; every sync DB
   call serialized all other requests waiting on the event loop.

2. **SQLite has no real write concurrency.** File locking serialized writes;
   connection reuse across coroutines caused `database is locked` errors.

## Solution: Dual-Engine Async Architecture

Replaced the single sync SQLAlchemy engine with a **dual-engine** approach:

| Engine | Session factory | Used by |
| --- | --- | --- |
| `async_engine` (`asyncpg` / `aiosqlite`) | `AsyncSessionLocal` | All FastAPI route handlers (via DI) |
| `sync_engine` (`psycopg2` / `sqlite3`) | `SyncSessionLocal` | Background audio-processing tasks only (run in thread pool) |

Background tasks (`audio_processing_service.py`, `whisperx_wrapper_service.py`) run
in `asyncio.get_event_loop().run_in_executor()` thread pools and **cannot** use async
DB connections — hence the sync engine is kept exclusively for them.

### Key implementation decisions

- **URL rewriting** at startup: `sqlite://` → `sqlite+aiosqlite://`,
  `postgresql://` → `postgresql+asyncpg://`
- **`NullPool`** for the SQLite async engine — SQLite connection objects are not safe
  across coroutines; pooling causes `database is locked`. `NullPool` creates/destroys
  a connection per request.
- **`StaticPool`** for in-memory SQLite in test fixtures — all connections must share
  the same in-memory database; `NullPool` would give each connection an empty DB.
- **`expire_on_commit=False`** on `async_sessionmaker` — prevents implicit lazy-loads
  after `commit()` which raise `MissingGreenlet` in async context.
- **Session lifecycle in `dependencies.py`**: `async with _container.db_session_factory() as session:`
  — each request gets its own session, committed or rolled back at request end.

### Files changed

| File | Change |
| --- | --- |
| `app/infrastructure/database/connection.py` | Dual engine, URL rewriting, NullPool/StaticPool |
| `app/infrastructure/database/repositories/sqlalchemy_task_repository.py` | Split: `AsyncSQLAlchemyTaskRepository` + `SyncSQLAlchemyTaskRepository` |
| `app/domain/repositories/task_repository.py` | Protocol: all methods `async def` |
| `app/services/task_management_service.py` | All methods `async def` with `await` |
| `app/api/dependencies.py` | Async generators owning session lifecycle |
| `app/api/task_api.py`, `audio_api.py`, `audio_services_api.py` | `await` on all repository/service calls |
| `app/core/container.py` | Wires `AsyncSQLAlchemyTaskRepository` + `AsyncSessionLocal` |
| `app/main.py` | Async `create_all` in lifespan, async `readiness_check` |
| `app/services/audio_processing_service.py` | Uses `SyncSessionLocal` / `SyncSQLAlchemyTaskRepository` |
| `app/services/whisperx_wrapper_service.py` | Same as above |
| `pyproject.toml` | Added `aiosqlite`, `asyncpg`, `pytest-asyncio>=0.24.0`, `sqlalchemy[asyncio]`, `asyncio_mode="auto"` |

---

## Load Test Results

Tests run with [Locust](https://locust.io/) against a single-worker uvicorn process,
hitting `/task/all` (DB read), `/health/ready` (DB ping), and `/health` (no DB).

### SQLite backend (`DB_URL=sqlite:///records.db`)

| Users | Failure rate | `/task/all` p50 | `/health/ready` p50 | Throughput |
| --- | --- | --- | --- | --- |
| Pre-migration ~20 | **~100%** | — | — | — |
| 200 | 0% | 11 s | 250 ms | ~15 req/s |
| 500 | 0% | 20 s | 500 ms | ~17 req/s |
| 300 (60 s run) | 0% | 31 s | 2.2 s | ~15 req/s |
| 1000 | 0% (soft hang) | never returns | 15 s | ~11 req/s |

**Bottleneck:** SQLite's single-writer file lock serializes all queries. No hard
failures after the migration, but `/task/all` degrades to unusable latency above ~300
concurrent users.

### PostgreSQL backend (`DB_URL=postgresql://postgres:test@localhost/testdb`)

Single Docker container (`postgres:16`), `pool_size=15`, `max_overflow=30`.

| Users | Failure rate | `/task/all` p50 | `/health/ready` p50 | Throughput |
| --- | --- | --- | --- | --- |
| 200 | 0% | 6 ms | 6 ms | 355 req/s |
| 500 | 0% | 360 ms | 390 ms | 481 req/s |
| 1000 | 0% | 1.0 s | 1.1 s | 593 req/s |
| 2000 | 0% | 2.3 s | 2.3 s | 621 req/s |
| 5000 | 0% | 5.2 s | 5.3 s | 620 req/s |

**Throughput ceiling ~620 req/s** is the single uvicorn worker's Python event loop
limit — not the database. To scale further: add `--workers N` to uvicorn (one worker
per CPU core) or deploy behind gunicorn with multiple uvicorn workers.

### Summary

| Metric | Before | After (SQLite) | After (PostgreSQL) |
| --- | --- | --- | --- |
| Breaking point | **20 users** (hard 503) | No hard failures | No hard failures |
| `QueuePool exhaustion` | Yes | Eliminated | Eliminated |
| `/task/all` p50 @ 200 users | — | 11 s | **6 ms** |
| Throughput @ 200 users | — | ~15 req/s | **355 req/s** |
| Scalability ceiling | Pool (45 conns) | SQLite file lock | ~620 req/s (event loop) |

---

## Running Load Tests

```bash
# Start the server (PostgreSQL recommended)
DB_URL=postgresql://postgres:test@localhost/testdb \
  uvicorn app.main:app --host 127.0.0.1 --port 8000

# Run locust headless
uv run locust -f tests/load/locustfile.py --headless \
  --users 500 --spawn-rate 20 --run-time 30s \
  --host http://127.0.0.1:8000

# Interactive UI at http://localhost:8089
uv run locust -f tests/load/locustfile.py --host http://127.0.0.1:8000
```

To start a PostgreSQL instance for local testing:

```bash
docker run -d --name pg-load-test \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=test -e POSTGRES_DB=testdb \
  -p 5432:5432 postgres:16
```
