#!/bin/bash
# Create a new migration with Alembic
set -e

# Validate environment
if [ -z "$DB_URL" ]; then
    echo "Error: DB_URL environment variable not set"
    echo "Example: export DB_URL=sqlite:///records.db"
    exit 1
fi

# Get migration message
if [ -z "$1" ]; then
    echo "Usage: ./scripts/create_migration.sh 'migration message'"
    echo "Example: ./scripts/create_migration.sh 'Add user_id to tasks'"
    exit 1
fi

MESSAGE="$1"

# Generate migration
echo "Generating migration: $MESSAGE"
echo "Database URL: $DB_URL"
alembic revision --autogenerate -m "$MESSAGE"

echo ""
echo "Migration created successfully!"
echo "Review the generated file in alembic/versions/"
echo ""
echo "To apply the migration:"
echo "  ./scripts/upgrade_db.sh"
