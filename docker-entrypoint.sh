#!/bin/bash
# Docker entrypoint script
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
exec gunicorn --bind 0.0.0.0:8000 \
    --workers 1 \
    --timeout 0 \
    --log-config gunicorn_logging.conf \
    app.main:app \
    -k uvicorn.workers.UvicornWorker
