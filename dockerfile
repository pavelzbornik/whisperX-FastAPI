FROM nvidia/cuda:12.8.0-base-ubuntu22.04

ENV PYTHON_VERSION=3.11

RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y update \
    && apt-get -y install --no-install-recommends \
    python${PYTHON_VERSION} \
    python3-pip \
    ffmpeg \
    git \
    wget

RUN wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb \
    && dpkg -i cuda-keyring_1.1-1_all.deb \
    && apt-get update \
    && apt-get -y install cudnn \
    && apt-get -y install libcudnn8

RUN ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 && \
    ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python && \
    ln -s -f /usr/bin/pip3 /usr/bin/pip

WORKDIR /app

RUN pip install -U pip setuptools --no-cache-dir


RUN pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 -i https://download.pytorch.org/whl/cu124 --no-cache-dir

COPY requirements requirements
RUN pip install --no-cache -r requirements/prod.txt

COPY app app
COPY tests tests

EXPOSE 8000
COPY app/gunicorn_logging.conf .
ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "0", "--log-config", "gunicorn_logging.conf", "app.main:app", "-k", "uvicorn.workers.UvicornWorker"]
