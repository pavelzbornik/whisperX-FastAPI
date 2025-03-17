FROM nvidia/cuda:12.8.1-base-ubuntu22.04

ENV PYTHON_VERSION=3.11

# Install dependencies and clean up in the same layer
RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y update \
    && apt-get -y install --no-install-recommends \
    python${PYTHON_VERSION} \
    python3-pip \
    git \
    ffmpeg \
    libcudnn8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 \
    && ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python

# Install UV for package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy application code
COPY app app/
COPY tests tests/
COPY app/gunicorn_logging.conf .
COPY requirements requirements/

# Install Python dependencies using UV
RUN uv pip install --system -U pip setuptools --no-cache-dir \
    && uv pip install --system torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 -i https://download.pytorch.org/whl/cu124 --no-cache-dir \
    && uv pip install --system --no-cache-dir -r requirements/prod.txt \
    # Clean pip cache and temporary files
    && rm -rf /root/.cache /tmp/*

EXPOSE 8000

ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "0", "--log-config", "gunicorn_logging.conf", "app.main:app", "-k", "uvicorn.workers.UvicornWorker"]
