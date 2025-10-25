#!/bin/bash
# Downgrade database migrations
set -e

if [ -z "$1" ]; then
    echo "Usage: ./scripts/downgrade_db.sh <revision>"
    echo ""
    echo "Examples:"
    echo "  ./scripts/downgrade_db.sh -1        # Downgrade one version"
    echo "  ./scripts/downgrade_db.sh base      # Downgrade to beginning"
    echo "  ./scripts/downgrade_db.sh b66b17122860  # Downgrade to specific revision"
    echo ""
    echo "To see migration history:"
    echo "  alembic history"
    exit 1
fi

REVISION="$1"

# Check if DB_URL is set
if [ -z "$DB_URL" ]; then
    echo "Warning: DB_URL not set, using default from config"
fi

echo "Downgrading database to: $REVISION"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Downgrade cancelled"
    exit 0
fi

alembic downgrade "$REVISION"

echo "✓ Downgrade completed successfully"
