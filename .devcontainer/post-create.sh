#!/bin/bash
set -e
# Source the environment to get uv in PATH
# echo "Sourcing environment..."
# export PATH="$HOME/.local/bin:$PATH"

echo "Verifying uv is in PATH..."
which uv

# System dependencies (openjdk, postgresql-client) are pre-installed in the dev stage

# Wait for PostgreSQL sidecar to be ready (provided by docker-compose devcontainer)
if [[ -n "$TEST_DB_URL" ]]; then
  echo "Waiting for PostgreSQL to be ready..."
  until pg_isready -h postgres -U postgres; do
    sleep 1
  done
  echo "PostgreSQL is ready."
fi

# Verify Java installation
java -version

# Install dependencies from pyproject.toml with dev extras
uv sync --all-extras

# Install ctranslate2 to maintain compatibility with libcudnn9-cuda-12
uv pip install ctranslate2==4.6.0 --system

git init
uv run pre-commit install

uv run pre-commit autoupdate || true

# Run pre-commit on all files in the repository
uv run pre-commit run --all-files || true

# Install Claude Code CLI
if ! command -v npm &>/dev/null; then
  echo "Error: npm not found — skipping Claude Code CLI installation" >&2
else
  npm install -g @anthropic-ai/claude-code
fi

# Add cclaude alias (IS_SANDBOX=1 enables isolation; --dangerously-skip-permissions
# allows unrestricted execution within the sandbox — safe inside a devcontainer)
CCLAUDE_ALIAS='alias cclaude="IS_SANDBOX=1 claude --dangerously-skip-permissions"'
grep -qF 'alias cclaude' /root/.bashrc 2>/dev/null || echo "$CCLAUDE_ALIAS" >> /root/.bashrc || true

# Authenticate GitHub CLI if not already logged in (token persisted in whisperx-gh-config volume)
if ! gh auth status &>/dev/null; then
  echo "GitHub CLI not authenticated. Starting interactive login..."
  gh auth login
fi
