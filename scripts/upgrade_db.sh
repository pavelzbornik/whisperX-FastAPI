#!/bin/bash
# Apply database migrations
set -e

echo "Applying database migrations..."

# Check if DB_URL is set
if [ -z "$DB_URL" ]; then
    echo "Warning: DB_URL not set, using default from config"
fi

alembic upgrade head

echo "✓ Migrations applied successfully"
