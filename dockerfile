# ---- Stage 1: base ----
# Shared foundation for both dev and production stages
FROM nvidia/cuda:13.0.1-base-ubuntu24.04 AS base

ENV PYTHON_VERSION=3.12
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH

# Install system dependencies and clean up in the same layer
# hadolint ignore=DL3008
RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y update \
    && apt-get -y install --no-install-recommends \
    python3.12 \
    libpython3.12 \
    git \
    ffmpeg \
    libcudnn9-cuda-12 \
    libatomic1 \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 \
    && ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python

# Install UV for package management
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /bin/

WORKDIR /app

# ---- Stage 2: dev (devcontainer target) ----
# Pre-installs dev dependencies and tools so devcontainer startup is fast
FROM base AS dev

# Install dev system dependencies (SonarLint requires Java 17+, pg_isready for healthcheck)
# hadolint ignore=DL3008
RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y update \
    && apt-get -y install --no-install-recommends \
    openjdk-17-jre-headless \
    postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Pre-install all dependencies (including dev extras) to warm cache
# Devcontainer mounts source as volume, so no COPY app/ needed
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --all-extras --no-install-project

# ---- Stage 3: production (default) ----
# Lean image with only runtime dependencies
FROM base AS production

# Layer 1: Install Python dependencies (cached unless pyproject.toml/uv.lock change)
# UV automatically selects CUDA 12.8 wheels on Linux
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra postgres \
    && rm -rf /root/.cache /tmp/* /root/.uv /var/cache/* \
    && find /usr/local -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local -type f -name '*.pyc' -delete \
    && find /usr/local -type f -name '*.pyo' -delete

# Layer 2: NLTK data (cached, depends only on nltk package not app code)
ENV NLTK_DATA=/app/nltk_data
RUN uv run --no-sync python -c "import nltk; \
    nltk.download('punkt', download_dir='/app/nltk_data', quiet=False); \
    nltk.download('punkt_tab', download_dir='/app/nltk_data', quiet=False)"

# Layer 3: Application code (rebuilds on code changes — cheap)
COPY app app/

EXPOSE 8000

# Health check to verify the application is responsive
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl --fail http://localhost:8000/health || exit 1

ENTRYPOINT ["uv", "run", "--no-sync", "gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "0", "app.main:app", "-k", "uvicorn.workers.UvicornWorker"]
