#!/bin/bash


# Install dependencies to make sure the env is up to date
uv pip install --system -r requirements/dev.txt
# Install ctranslate2 to maintain compatibility with libcudnn9-cuda-12
uv pip install ctranslate2==4.6.0 --system
