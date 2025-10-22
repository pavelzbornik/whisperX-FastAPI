# Copilot Instructions for whisperX-FastAPI

## Repository Overview

**whisperX-FastAPI** is a REST API service built with FastAPI that provides audio/video transcription, alignment, speaker diarization, and transcript combination using WhisperX. The service processes audio files asynchronously using background tasks with results stored in a database.

**Repository Stats:**

- **Primary Language:** Python 3.11
- **Framework:** FastAPI 0.117+
- **ML Library:** whisperx 3.7.2
- **Package Manager:** `uv` (Astral's fast Python package manager)
- **Container Runtime:** Docker with NVIDIA CUDA 12.8+ support
- **Database:** SQLAlchemy ORM (default: SQLite, supports PostgreSQL/MySQL via `DB_URL`)
- **Target Environment:** Linux with NVIDIA GPU or CPU fallback

## Project Architecture

### Directory Structure

```text
├── app/                          # Main application code
│   ├── main.py                   # FastAPI app entry point with health checks
│   ├── config.py                 # Environment config (HF_TOKEN, WHISPER_MODEL, DEVICE, etc.)
│   ├── models.py                 # SQLAlchemy database models
│   ├── schemas.py                # Pydantic schemas for API validation
│   ├── db.py                     # Database engine and session management
│   ├── tasks.py                  # Background task definitions
│   ├── services.py               # Core business logic
│   ├── whisperx_services.py      # WhisperX integration layer
│   ├── audio.py                  # Audio file processing utilities
│   ├── files.py                  # File upload/download handling
│   ├── transcript.py             # Transcript processing utilities
│   ├── logger.py                 # Logging configuration
│   ├── warnings_filter.py        # Warning suppression filter
│   ├── uvicorn_log_conf.yaml     # Uvicorn logging config
│   ├── gunicorn_logging.conf     # Gunicorn logging config (used in Docker)
│   ├── routers/                  # API route handlers
│   │   ├── stt.py                # Speech-to-text endpoints
│   │   ├── stt_services.py       # Individual service endpoints
│   │   └── task.py               # Task management endpoints
│   └── docs/                     # Auto-generated documentation
│       ├── openapi.json/yaml     # OpenAPI spec dumps
│       └── db_schema.md          # Database schema documentation
├── tests/                        # Test suite
│   ├── test_all.py               # Main integration tests
│   ├── test_whisperx_services.py # WhisperX service unit tests
│   ├── pytest.ini                # Pytest configuration
│   └── test_files/               # Test audio/transcript fixtures
├── .github/                      # CI/CD configuration
│   ├── workflows/
│   │   ├── CI.yaml               # Main CI pipeline (lint, test, build, scan)
│   │   ├── gitleaks.yaml         # Secret scanning
│   │   └── precommit-autoupdate.yml # Weekly pre-commit hook updates
│   └── actions/
│       └── setup/action.yaml     # Reusable setup action (Python, uv, deps)
├── pyproject.toml                # Project metadata and dependencies
├── uv.lock                       # Locked dependency versions (DO NOT edit manually)
├── dockerfile                    # Production container image
├── docker-compose.yml            # Container orchestration
├── start.sh                      # Docker compose restart script
└── .pre-commit-config.yaml       # Pre-commit hooks configuration
```

### Key Configuration Files

- **`.env`** (not in repo, create locally): Required environment variables
- **`pyproject.toml`**: Dependencies, tool configs (ruff, coverage, codespell)
- **`.pre-commit-config.yaml`**: Pre-commit hooks (ruff, yamllint, hadolint, gitleaks, etc.)
- **`.markdownlint.json`**: Markdown linting rules
- **`.gitleaks.toml`**: Secret scanning configuration

## Environment Setup

### Required Environment Variables (`.env` file)

Create a `.env` file in the repository root with these variables:

```bash
HF_TOKEN=<your-huggingface-token>       # Required for model downloads
WHISPER_MODEL=tiny                      # Model size: tiny/base/small/medium/large/distil-*
DEFAULT_LANG=en                         # Default transcription language
DEVICE=cuda                             # cuda or cpu (CI uses cpu)
COMPUTE_TYPE=float16                    # float16/float32/int8 (MUST use int8 for CPU)
LOG_LEVEL=INFO                          # DEBUG/INFO/WARNING/ERROR
ENVIRONMENT=production                  # production or development
DEV=true                                # Boolean for dev mode
FILTER_WARNING=true                     # Filter specific warnings
DB_URL=sqlite:///records.db             # Database connection string
```

**CRITICAL:** When `DEVICE=cpu`, you MUST set `COMPUTE_TYPE=int8` or WhisperX will fail.

## Build and Development Commands

### Installing Dependencies

This project uses `uv` (not pip or poetry). **ALWAYS use `uv` for all package operations.**

```bash
# Install production dependencies only
uv sync --no-dev

# Install all dependencies including dev tools (linters, tests)
uv sync

# Install all extras (includes dev group)
uv sync --all-extras
```

**CRITICAL:** `uv sync` respects `uv.lock`. The lock file contains platform-specific PyTorch builds:

- Linux x86_64: CUDA 12.8 wheels from PyTorch index
- macOS/ARM: CPU-only wheels
- Never manually edit `uv.lock`

### Running the Application

**Local development (Uvicorn):**

```bash
# Make sure .env file exists first
uvicorn app.main:app --reload --log-config app/uvicorn_log_conf.yaml --log-level $LOG_LEVEL
```

**Docker (Gunicorn):**

```bash
# Quick restart with logs
./start.sh

# Or manually with compose
docker-compose up -d
docker-compose logs -f

# Or direct Docker build
docker build -t whisperx-service .
docker run -d --gpus all -p 8000:8000 --env-file .env whisperx-service
```

**Key Differences:**

- Local runs with Uvicorn (single worker, auto-reload)
- Docker runs with Gunicorn + Uvicorn workers (production config)
- Docker entrypoint: `gunicorn --bind 0.0.0.0:8000 --workers 1 --timeout 0 --log-config gunicorn_logging.conf app.main:app -k uvicorn.workers.UvicornWorker`

## Testing

### Running Tests

**ALWAYS run tests through `uv run` (not plain pytest):**

```bash
# Run all tests with coverage (CI requirement: ≥80%)
uv run pytest --cov=app --cov-report=xml --cov-report=term --cov-fail-under=80

# Run specific test file
uv run pytest tests/test_all.py

# Run with JUnit XML report (for CI)
uv run pytest --junitxml=pytest-report.xml --cov=app --cov-report=xml --cov-fail-under=80
```

**Test Environment Setup:**

- Tests automatically use in-memory SQLite: `sqlite:///:memory:`
- Tests require `DEVICE=cpu` and `COMPUTE_TYPE=int8` (set in CI)
- Tests download tiny model on first run (cached in `~/.cache`)
- Some tests are slow (transcription takes 10-20s per test)

**Coverage Requirements:**

- Minimum coverage: 80% (enforced by CI on `test` job)
- Coverage config in `pyproject.toml` under `[tool.coverage.*]`
- Omits: `tests/*`, `/tmp/*`, `venv/*`, virtualenv, site-packages

## Linting and Formatting

### Pre-commit Hooks

**CRITICAL:** All code MUST pass pre-commit checks before merge. CI runs full validation.

```bash
# Install pre-commit hooks (one-time setup)
uv run pre-commit install

# Run all hooks on all files
uv run pre-commit run --all-files

# Run specific hook
uv run pre-commit run ruff --all-files
uv run pre-commit run hadolint --all-files
```

### Ruff (Linter + Formatter)

Ruff replaces flake8, isort, and black. **ALWAYS run through `uv`:**

```bash
# Check for issues (read-only)
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check --fix .

# Check formatting
uv run ruff format --check .

# Apply formatting
uv run ruff format .
```

**CI Behavior:** The `lint` job runs `pre-commit run --all-files` which includes:

- `ruff check --fix` (auto-fix enabled)
- `ruff format` (formatting)
- `mypy` (strict type checking - must have zero errors)
- `yamllint` (YAML validation)
- `hadolint` (Dockerfile linting)
- `markdownlint --fix` (Markdown formatting)
- `codespell` (spell checking)
- `gitleaks` (secret detection)
- `shellcheck` (shell script validation)
- `pydocstyle` (docstring validation)

### Hadolint (Dockerfile Linting)

**Install before running pre-commit:**

```bash
wget -O /usr/local/bin/hadolint https://github.com/hadolint/hadolint/releases/download/v2.12.0/hadolint-Linux-x86_64
chmod +x /usr/local/bin/hadolint
```

CI installs this automatically in the `lint` job.

## CI/CD Pipeline

### GitHub Actions Workflows

**Main CI Pipeline (`.github/workflows/CI.yaml`):**

The CI runs on PRs and pushes to `main`/`dev` branches when these paths change:

- `app/**`
- `tests/**`
- `dockerfile`
- `docker-compose.yml`
- `pyproject.toml`

**CI Jobs (must all pass):**

1. **`lint`** (15 min timeout):
   - Runs `pre-commit run --all-files`
   - Installs hadolint v2.12.0
   - Comments on PR if fails with link to logs

2. **`test`** (20 min timeout):
   - Python 3.11 matrix
   - Runs with `DEVICE=cpu`, `COMPUTE_TYPE=int8`
   - Requires ≥80% coverage
   - Uploads test report (JUnit XML) and coverage report (XML) as artifacts
   - Comments on PR if fails

3. **`dependency-review`** (10 min timeout, PR only):
   - Scans for vulnerable dependencies
   - Fails on moderate+ severity
   - Comments on PR if fails

4. **`build`** (30 min timeout, PR only):
   - Builds Docker image
   - Runs Trivy security scan (CRITICAL/HIGH vulns)
   - Uploads SARIF to GitHub Security
   - Outputs scan results to job summary
   - Comments on PR if fails

5. **`dependabot-auto-merge`** (runs after build/test/dependency-review):
   - Auto-merges Dependabot PRs if all checks pass

6. **`release-please`** (main branch only):
   - Creates release PRs using conventional commits
   - Updates `uv.lock` automatically

**Other Workflows:**

- **`gitleaks.yaml`**: Scans for secrets on all pushes/PRs
- **`precommit-autoupdate.yml`**: Weekly cron to update pre-commit hooks

### Common Setup Action

All CI jobs use `.github/actions/setup/action.yaml`:

```yaml
steps:
  - Install system deps: ffmpeg, libblas3
  - Install uv (with cache enabled)
  - Set up Python 3.11
  - Run: uv sync --all-extras
```

**Reproducibility:** To match CI environment locally:

```bash
sudo apt-get update && sudo apt-get install -y ffmpeg libblas3
uv sync --all-extras
```

## Common Issues and Workarounds

### 1. DEVICE/COMPUTE_TYPE Mismatch

**Symptom:** WhisperX crashes with CUDA errors or dtype errors.
**Fix:** When using `DEVICE=cpu`, MUST set `COMPUTE_TYPE=int8`.

### 2. uv.lock Out of Sync

**Symptom:** Dependency resolution errors or CI failures.
**Fix:** Run `uv lock` to regenerate lock file. Commit the changes.

### 3. Pre-commit Hook Failures

**Symptom:** Hooks fail locally but you can't reproduce.
**Fix:**

```bash
uv run pre-commit clean  # Clear hook cache
uv run pre-commit install --install-hooks  # Reinstall
uv run pre-commit run --all-files  # Test
```

### 4. Hadolint Not Found

**Symptom:** Pre-commit fails on hadolint hook.
**Fix:** Install hadolint binary (see Linting section above).

### 5. Tests Timeout

**Symptom:** Tests hang or timeout in CI.
**Fix:** Tests can take 10-20s per transcription. Use `tiny` model. CI has 20 min timeout.

### 6. Docker GPU Not Available

**Symptom:** Docker can't access GPU.
**Fix:**

- Host MUST have NVIDIA drivers 12.8+ installed
- Use `nvidia-docker2` runtime
- Verify with: `docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi`

### 7. Model Download Failures

**Symptom:** "401 Unauthorized" or download hangs.
**Fix:**

- Set valid `HF_TOKEN` in `.env`
- Models cache in `~/.cache/huggingface/hub` and `~/.cache/torch`
- Docker: Mount volumes to persist cache (see docker-compose.yml)

## Code Change Validation Checklist

Before committing changes, ALWAYS:

1. **Add complete type annotations:**
   - All function parameters must have type hints
   - All functions must have return type annotations
   - Use modern syntax: `dict[str, Any]`, `list[str]`, `str | None` (Python 3.10+)

2. **Validate type checking with mypy:**

   ```bash
   uv run mypy app/  # Must show: Success: no issues found
   ```

3. **Run linting and formatting:**

   ```bash
   uv run ruff check --fix .
   uv run ruff format .
   ```

4. **Run tests with coverage:**

   ```bash
   uv run pytest --cov=app --cov-report=term --cov-fail-under=80
   ```

5. **Run all pre-commit hooks (includes mypy, ruff, and other checks):**

   ```bash
   uv run pre-commit run --all-files
   ```

6. **For Dockerfile changes:**

   ```bash
   hadolint dockerfile
   docker build -t whisperx-service .  # Verify build succeeds
   ```

7. **For dependency changes:**

   ```bash
   uv lock  # Regenerate uv.lock
   uv sync --all-extras  # Test installation
   ```

8. **Verify .env is NOT committed:**

   ```bash
   git status  # .env should not appear
   ```

## Important Development Notes

- **NEVER commit `.env`**: Contains secrets (HF_TOKEN). Ignored by git.
- **NEVER manually edit `uv.lock`**: Regenerate with `uv lock`.
- **All Python commands MUST use `uv run`**: Direct `pytest`, `ruff`, `mypy` etc. won't work.
- **Type annotations are REQUIRED on all functions**: mypy with `disallow_untyped_defs` enforces this in pre-commit and CI.
- **mypy must pass with zero errors**: Type checking is mandatory before merge.
- **Coverage threshold is 80%**: Tests will fail below this.
- **Docker uses Gunicorn, not Uvicorn**: Entrypoint differs from local dev.
- **PyTorch wheels are platform-specific**: `uv.lock` handles this via index selection.
- **CI runs on dev and main branches**: PRs trigger full pipeline.
- **Pre-commit hooks auto-fix where possible**: ruff, markdownlint have `--fix` enabled; mypy validates (no auto-fix).
- **Health checks available:** `/health`, `/health/live`, `/health/ready` for monitoring.
- **Type stubs required:** pandas-stubs, types-requests, types-PyYAML must be installed via uv sync.

## Trust These Instructions

These instructions are comprehensive and validated. Only search for additional information if:

- Instructions conflict with actual behavior
- New files/tools are introduced not covered here
- Error messages suggest outdated information

Otherwise, trust this document and proceed with implementation.
