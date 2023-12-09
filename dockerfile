FROM nvidia/cuda:11.8.0-base-ubuntu22.04

ENV PYTHON_VERSION=3.11

RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y update \
    && apt-get -y install --no-install-recommends \
    python${PYTHON_VERSION} \
    python3-pip \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 && \
    ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python && \
    ln -s -f /usr/bin/pip3 /usr/bin/pip

WORKDIR /app

RUN pip install -U pip setuptools --no-cache-dir


COPY . .

RUN pip install torch==2.0.1 torchvision==0.15.2  torchaudio==2.0.2 -i https://download.pytorch.org/whl/cu118 --no-cache-dir
RUN pip install git+https://github.com/m-bain/whisperx.git --no-cache-dir


RUN pip install -r requirements.txt --no-cache-dir

EXPOSE 9000
ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:9000", "--workers", "1", "--timeout", "0", "app.main:app", "-k", "uvicorn.workers.UvicornWorker"]