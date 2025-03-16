#!/bin/bash
set -e
# Source the environment to get uv in PATH
echo "Sourcing environment..."
export PATH="$HOME/.local/bin:$PATH"

echo "Verifying uv is in PATH..."
which uv

uv pip install --system -r requirements/dev.txt

git init
pre-commit install

pre-commit autoupdate

# Run pre-commit on all files in the repository
pre-commit run --all-files || true
