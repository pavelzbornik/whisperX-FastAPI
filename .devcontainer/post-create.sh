#!/bin/bash
set -e
# Source the environment to get uv in PATH
# echo "Sourcing environment..."
# export PATH="$HOME/.local/bin:$PATH"

echo "Verifying uv is in PATH..."
which uv

# Install system dependencies needed for pre-commit hooks
apt-get update && apt-get install -y libatomic1

# Install dependencies from pyproject.toml with dev extras
uv sync --all-extras

# Install ctranslate2 to maintain compatibility with libcudnn9-cuda-12
uv pip install ctranslate2==4.6.0 --system

git init
uv run pre-commit install

uv run pre-commit autoupdate

# Run pre-commit on all files in the repository
uv run pre-commit run --all-files || true
