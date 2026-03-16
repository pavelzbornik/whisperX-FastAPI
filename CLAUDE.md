# Project Guide

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**whisperX-FastAPI** is a REST API built with FastAPI that provides async audio/video transcription, alignment, speaker diarization, and transcript combination using WhisperX. Tasks are processed as background jobs with results tracked in a database.

- **Package manager:** `uv` — always use `uv run` for all Python commands
- **Database:** SQLAlchemy ORM (default: SQLite, configurable via `DB_URL`)
- **Container runtime:** Docker with NVIDIA CUDA (CPU fallback supported)
- See `pyproject.toml` for exact Python and dependency versions.

## Commands

### Install dependencies

```bash
uv sync --all-extras   # includes dev tools (linters, tests)
uv sync --no-dev       # production only
```

### Run locally

```bash
uvicorn app.main:app --reload --log-config app/uvicorn_log_conf.yaml
```

### Run with Docker

```bash
./start.sh             # quick restart with logs
docker-compose up -d
```

### Test

```bash
# All tests with coverage (CI requires ≥80%)
uv run pytest --cov=app --cov-report=term --cov-fail-under=80

# Single test file
uv run pytest tests/unit/domain/entities/test_task.py

# By marker (unit/integration/e2e/slow)
uv run pytest -m unit
uv run pytest -m "not slow"
```

### Lint and format

```bash
uv run ruff check --fix .
uv run ruff format .
uv run mypy app/           # must show: Success: no issues found
uv run pre-commit run --all-files
```

### Dependency changes

```bash
uv lock                # regenerate uv.lock after editing pyproject.toml
uv sync --all-extras   # test install
```

## Architecture

Layered Architecture with Repository Pattern and Dependency Injection Container
(`dependency-injector` library). Each folder below has its own `CLAUDE.md` with
layer-specific guidance.

```text
app/
├── main.py                    # FastAPI app, lifespan, health endpoints, router registration
├── api/                       # HTTP layer: routers, schemas, mappers, DI wiring
│   ├── audio_api.py           # Speech-to-text (full pipeline) endpoints
│   ├── audio_services_api.py  # Individual service endpoints (transcribe/align/diarize)
│   ├── task_api.py            # Task management endpoints
│   ├── dependencies.py        # Injects services from Container via Depends()
│   ├── schemas/               # Pydantic request/response models
│   ├── mappers/               # API schema ↔ domain entity conversion
│   └── exception_handlers.py  # Maps domain exceptions → HTTP responses
├── core/                      # Config, DI Container, exception hierarchy → see app/core/CLAUDE.md
├── domain/                    # Pure Python entities, repository + ML service interfaces → see app/domain/CLAUDE.md
├── infrastructure/            # SQLAlchemy + WhisperX implementations → see app/infrastructure/CLAUDE.md
└── services/                  # Business logic orchestration → see app/services/CLAUDE.md

tests/                         # Markers, mocks, factories, coverage → see tests/CLAUDE.md
docs/                          # ADRs, stories, config migration guide → see docs/CLAUDE.md
```

## Environment Variables

Create a `.env` file in the repo root:

```bash
HF_TOKEN=<huggingface-token>     # required for diarization model downloads
WHISPER_MODEL=tiny               # tiny/base/small/medium/large/distil-*
DEFAULT_LANG=en
DEVICE=cuda                      # cuda or cpu
COMPUTE_TYPE=float16             # float16/float32/int8 — MUST be int8 when DEVICE=cpu
LOG_LEVEL=INFO
ENVIRONMENT=production
DB_URL=sqlite:///records.db
```

**Critical:** When `DEVICE=cpu`, `COMPUTE_TYPE` is auto-corrected to `int8`. Tests set
`DEVICE=cpu` and `COMPUTE_TYPE=int8` automatically.

## CI Pipeline

`.github/workflows/CI.yaml` triggers on PRs and pushes to `main`/`dev` when `app/`,
`tests/`, `dockerfile`, `docker-compose.yml`, or `pyproject.toml` change.

Jobs: **lint** → **test** (≥80% coverage) → **dependency-review** + **build** (Docker +
Trivy scan) → **release-please** (main only).

Dependency updates (including pre-commit hooks, GitHub Actions, Docker images, and uv
packages) are managed by Renovate (`renovate.json`). Updates are batched monthly; ML-critical
packages (PyTorch, huggingface-hub, whisperx) require manual review.

**PyTorch wheels:** `uv.lock` is platform-specific (CUDA on Linux x86\_64, CPU on
macOS/Windows). Never manually edit `uv.lock`.
