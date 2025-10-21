#!/bin/bash
set -e

# Deactivate any active virtual environment to avoid Python version conflicts
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate 2>/dev/null || true
fi

# Disable pre-commit-uv integration to avoid version detection issues with Python rc versions
# export PRE_COMMIT_USE_UV=0

# Install dependencies to make sure the env is up to date
uv sync --all-extras
# Install ctranslate2 to maintain compatibility with libcudnn9-cuda-12
uv pip install ctranslate2==4.6.0 --system
