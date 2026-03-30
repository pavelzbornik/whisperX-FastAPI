# Project Guide

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**whisperX-FastAPI** is a REST API built with FastAPI that provides async audio/video transcription, alignment, speaker diarization, and transcript combination using WhisperX. Tasks are processed as background jobs with results tracked in a database.

- **Package manager:** `uv` — always use `uv run` for all Python commands
- **Database:** SQLAlchemy ORM (default: SQLite, configurable via `DB_URL`)
- **Container runtime:** Docker with NVIDIA CUDA (CPU fallback supported)
- See `pyproject.toml` for exact Python and dependency versions.

## Commands

All developer commands are defined in `Taskfile.yml` (with includes in `taskfiles/`).
Run `task --list` to see all available tasks. [go-task](https://taskfile.dev/) is
installed automatically via the devcontainer feature.

### Install dependencies

```bash
task deps              # includes dev tools (linters, tests)
task deps:prod         # production only
```

### Run locally

```bash
task run
```

### Run with Docker

```bash
task docker:restart    # stop, start, follow logs
task docker:up         # start in background
task docker:down       # stop
task docker:logs       # follow logs
```

### Test

```bash
task test              # all tests with coverage (CI requires ≥80%)
task test:unit         # unit tests only
task test:fast         # exclude slow and load markers
task test:ci           # full CI command with XML reports

# Single test file (use uv directly)
uv run pytest tests/unit/domain/entities/test_task.py
```

### Lint and format

```bash
task lint              # ruff check --fix
task format            # ruff format
task typecheck         # mypy app/
task check             # all three sequentially
task pre-commit        # run all pre-commit hooks
```

### Dependency changes

```bash
task deps:lock         # regenerate uv.lock + sync
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
MAX_CONCURRENT_GPU_TASKS=1          # max simultaneous GPU tasks (prevents OOM)
```

**Critical:** When `DEVICE=cpu`, `COMPUTE_TYPE` is auto-corrected to `int8`. Tests set
`DEVICE=cpu` and `COMPUTE_TYPE=int8` automatically.

## CI Pipeline

`.github/workflows/CI.yaml` triggers on PRs and pushes to `main`/`dev` when `app/`,
`tests/`, `dockerfile`, `docker-compose.yml`, or `pyproject.toml` change.

Jobs: **lint** → **test** (≥80% coverage) → **dependency-review** + **build** (Docker +
Trivy scan) → **release-please** (main only).

Dependency updates (uv packages, GitHub Actions, Docker images, pre-commit hooks) are
managed by Renovate (`renovate.json`), batched monthly. ML-critical packages (PyTorch,
huggingface-hub, whisperx) require manual review; minor/patch updates for all other
groups auto-merge after CI passes.

**PyTorch wheels:** `uv.lock` is platform-specific (CUDA on Linux x86\_64, CPU on
macOS/Windows). Never manually edit `uv.lock`.

## Testing — TDD Process

Follow Test-Driven Development for all new features and bug fixes:

### TDD Workflow

1. **Write failing tests first** — before writing any implementation code, write tests
   that define the expected behavior. Run them to confirm they fail.
2. **Implement the minimum code** to make the tests pass — no more, no less.
3. **Refactor** — clean up the implementation while keeping tests green.
4. **Repeat** for each new behavior or code path.

### Coverage Rules

- All new code must have tests written **before** implementation
- Run `task test` after every change — ensure coverage ≥80% overall
- Target >80% coverage on new code specifically (SonarCloud new code gate)
- Check coverage gaps proactively: `uv run pytest --cov=app --cov-report=term-missing`
- Never commit untested code paths — if you wrote it, test it first

### Test Organization

- Unit tests (`tests/unit/`) for isolated logic — mock all external deps
- E2e tests (`tests/e2e/`) for API endpoints — test full request/response cycle
- Integration tests (`tests/integration/`) for real DB or service interaction
- Use factories (`tests/factories/`) over inline object construction
- Use mocks (`tests/mocks/`) — extend existing mocks rather than adding conditional logic

### When Fixing Bugs

1. Write a test that reproduces the bug (must fail)
2. Fix the bug
3. Confirm the test passes
4. Check no regressions: `task test`

## Data Integrity

- When modifying file contents (especially Markdown/YAML frontmatter), validate that
  existing fields are preserved
- Never replace entire file contents when only a section needs updating
- For batch operations, process in small batches with validation between each

## PR Workflow

- Before creating a PR, run: `task check` (lint + format + typecheck) and `task test`
- Address style violations proactively — check for unused imports, consistent naming
  (`str | None` not `Optional[str]`), and docstrings on public methods
- Verify coverage meets threshold before pushing, not after CI fails
