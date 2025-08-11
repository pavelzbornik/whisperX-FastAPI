# whisperX-FastAPI Development Instructions

**Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

whisperX-FastAPI is a Python FastAPI application providing REST API services for speech-to-text transcription, alignment, diarization, and speaker identification using whisperX. The application supports both GPU (CUDA) and CPU processing modes.

## Critical Prerequisites & Network Requirements

**IMPORTANT**: This project has significant network dependencies that may fail in restricted environments:

- **PyPI access**: Required for installing Python dependencies (`pip install` operations)
- **PyTorch index**: Downloads from `https://download.pytorch.org/whl/`
- **NVIDIA CUDA repos**: Downloads from `developer.download.nvidia.com`
- **Hugging Face Hub**: Downloads AI models during runtime (requires `HF_TOKEN`)
- **GitHub/external URLs**: For model downloads and updates

**If network access is restricted**: Document this as a limitation. Commands requiring internet access will fail with timeout errors.

## Working Effectively

### Bootstrap and Environment Setup

**System Requirements:**
- Ubuntu 22.04+ (for Docker) or any Linux with Python 3.11/3.12
- ffmpeg: `sudo apt-get install -y ffmpeg libblas3`
- For GPU: CUDA 12.8+ drivers and compatible hardware
- For development: Python 3.11+ (Python 3.12 also works), Git, Docker

**Python Environment Setup:**
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate
python --version  # Should be 3.11+ or 3.12+
```

**Dependency Installation:**
```bash
# Install PyTorch first (CRITICAL - install before other dependencies)
# For CPU-only environments:
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# For CUDA environments (requires CUDA 12.8+):
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126

# Then install project dependencies:
# Production dependencies only:
pip install -r requirements/prod.txt

# Development dependencies (includes testing, linting):
pip install -r requirements/dev.txt
```

**TIMING**: PyTorch installation takes 3-5 minutes. Other dependencies take 5-10 minutes. **NEVER CANCEL** during installation - set timeout to 15+ minutes for pip install commands.

### Environment Configuration

**Create `.env` file** (required for all operations):
```bash
# Required - Get token from https://huggingface.co/settings/tokens
HF_TOKEN=your_huggingface_token_here
WHISPER_MODEL=tiny
DEFAULT_LANG=en
LOG_LEVEL=INFO
ENVIRONMENT=development
DEV=true
FILTER_WARNING=true

# Device configuration
DEVICE=cpu          # or "cuda" for GPU
COMPUTE_TYPE=int8   # for CPU, or "float16" for GPU

# Database (optional - defaults to sqlite:///records.db)
DB_URL=sqlite:///records.db
```

**CRITICAL**: Without a valid `HF_TOKEN`, model downloads will fail. Without `.env`, the application will not start.

## Build, Test, and Run

### Local Development Server

```bash
# Activate environment
source venv/bin/activate

# Run development server
uvicorn app.main:app --reload --log-config app/uvicorn_log_conf.yaml --log-level $LOG_LEVEL
```

**Startup time**: 30-60 seconds for CPU, 10-30 seconds for GPU. **NEVER CANCEL** - wait for "Application startup complete" message.

**Access**: Application available at `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

### Docker Build and Run

**Build Image** (CRITICAL - VERY LONG BUILD TIME):
```bash
# NEVER CANCEL: Docker build takes 15-45 minutes depending on network
# Set timeout to 60+ minutes for docker build commands
docker build -t whisperx-service .
```

**Run Container**:
```bash
# For CPU-only
docker run -d --env-file .env -p 8000:8000 whisperx-service

# For GPU support (requires CUDA 12.8+ on host)
docker run -d --gpus all --env-file .env -p 8000:8000 whisperx-service

# Using docker-compose (includes persistent model cache)
docker-compose up -d
```

**Model Cache**: First run downloads models (500MB-10GB depending on model size). Takes 5-30 minutes. **NEVER CANCEL** model downloads.

### Testing

**Run Test Suite**:
```bash
source venv/bin/activate

# Basic test run
pytest

# With coverage (required minimum: 55%)
coverage run --source=app -m pytest
coverage report --fail-under=55

# Specific test files
pytest tests/test_all.py
pytest tests/test_whisperx_services.py
```

**TIMING**: Test suite takes 5-15 minutes (includes model downloads on first run). **NEVER CANCEL** - set timeout to 20+ minutes for pytest commands.

**Test Requirements**:
- Tests use `tiny` model for speed
- Audio test file: `tests/test_files/audio_en.mp3` (must exist)
- CPU tests pass without GPU
- Some GPU-specific tests are skipped on CPU-only systems

### Linting and Code Quality

**Run Linting** (required before commits):
```bash
# Check code formatting and style
ruff check .
ruff format --check .

# Fix formatting automatically
ruff format .

# Pre-commit hooks (run all checks)
pre-commit run --all-files
```

**Coverage Report**:
```bash
coverage html  # Generates htmlcov/ directory
coverage report --fail-under=55  # CI requirement
```

## Validation Scenarios

**Always test these scenarios after making changes:**

### 1. Health Checks (Basic Validation)
```bash
curl http://127.0.0.1:8000/health          # Basic health
curl http://127.0.0.1:8000/health/live     # Liveness probe
curl http://127.0.0.1:8000/health/ready    # Readiness probe (includes DB)
```

### 2. Speech-to-Text Functionality
```bash
# Test transcription with sample audio
curl -X POST "http://127.0.0.1:8000/speech-to-text" \
  -F "file=@tests/test_files/audio_en.mp3"

# Check task status (use identifier from response)
curl http://127.0.0.1:8000/task/{identifier}
```

### 3. Model Loading Validation
- First request takes 30-120 seconds (model download/loading)
- Subsequent requests should be faster (2-10 seconds)
- Monitor logs for model loading messages

### 4. Database Functionality
- Check that tasks are stored: `curl http://127.0.0.1:8000/task/all`
- Verify SQLite database created: `ls -la records.db`

## Common Issues and Limitations

### Network/Firewall Issues
- **PyPI timeouts**: Cannot install dependencies in restricted networks
- **Model download failures**: Requires internet access to Hugging Face Hub
- **CUDA repo access**: Docker build needs NVIDIA package repositories

**Workaround**: Use pre-built Docker images or offline package management when network is restricted.

### Python Version Compatibility
- **Project specifies**: Python 3.11
- **Ubuntu 24.04 default**: Python 3.12
- **Compatibility**: Python 3.12 works but may have minor differences

### GPU vs CPU Configuration
- **CPU mode**: Set `DEVICE=cpu` and `COMPUTE_TYPE=int8`
- **GPU mode**: Set `DEVICE=cuda` and `COMPUTE_TYPE=float16`
- **Invalid combinations**: CPU with float16 will cause errors

### Model Size and Memory
- `tiny`: ~39MB, fast, lower accuracy
- `small`: ~244MB, balanced
- `medium`: ~769MB, good accuracy
- `large`: ~1550MB, best accuracy, requires 8GB+ RAM

## File Structure and Navigation

**Key directories:**
- `app/`: Main application code
  - `app/main.py`: FastAPI application entry point
  - `app/routers/`: API route handlers
  - `app/whisperx_services.py`: Core transcription logic
  - `app/config.py`: Configuration management
- `tests/`: Test suite and test data
  - `tests/test_files/`: Sample audio files for testing
- `requirements/`: Dependency definitions
  - `requirements/prod.txt`: Production dependencies
  - `requirements/dev.txt`: Development dependencies
- `.github/workflows/`: CI/CD workflows

**Important files:**
- `.env`: Environment configuration (create from template)
- `docker-compose.yml`: Container orchestration
- `pyproject.toml`: Project metadata and tool configuration

## CI/CD Workflow Requirements

**Before committing, always run:**
```bash
ruff check .                    # Linting
ruff format --check .          # Formatting
pytest                         # Tests
coverage report --fail-under=55 # Coverage check
```

**CI requirements:**
- Minimum 55% test coverage
- All ruff linting checks must pass
- All tests must pass
- Docker image must build successfully

**Branch strategy:**
- Main branch: production-ready code
- Dev branch: development integration
- Feature branches: individual changes

## Time Expectations and Timeouts

**NEVER CANCEL these operations - always wait for completion:**

- **PyTorch installation**: 3-5 minutes (timeout: 15+ minutes)
- **Full dependency install**: 5-15 minutes (timeout: 20+ minutes)
- **Docker build**: 15-45 minutes (timeout: 60+ minutes)
- **First model download**: 5-30 minutes depending on model size
- **Test suite execution**: 5-15 minutes (timeout: 20+ minutes)
- **Application startup**: 30-60 seconds with model loading

**Quick operations** (< 2 minutes):
- Linting with ruff: 10-30 seconds
- Health check responses: < 1 second
- Subsequent API requests: 2-10 seconds (after model loaded)