FROM nvidia/cuda:12.9.1-base-ubuntu22.04

ENV PYTHON_VERSION=3.11
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH

# Install dependencies and clean up in the same layer
RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y update \
    && apt-get -y install --no-install-recommends \
    python3.11=3.11.0~rc1-1~22.04 \
    python3-pip=22.0.2+dfsg-1ubuntu0.6 \
    git \
    ffmpeg=7:4.4.2-0ubuntu0.22.04.1 \
    libcudnn9-cuda-12=9.8.0.87-1 \
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
RUN pip install --upgrade pip setuptools && uv pip install --system --no-cache-dir -r requirements/system.txt -i https://download.pytorch.org/whl/cu126 \
    && uv pip install --system --no-cache-dir -r requirements/prod.txt \
    # Force install ctranslate2 version 4.6.0 or higher to maintain compatibility with libcudnn9-cuda-12
    && uv pip install ctranslate2==4.6.0 --system \
    # Clean pip cache and temporary files
    && rm -rf /root/.cache /tmp/*

EXPOSE 8000

ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "0", "--log-config", "gunicorn_logging.conf", "app.main:app", "-k", "uvicorn.workers.UvicornWorker"]
