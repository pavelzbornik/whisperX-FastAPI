#!/usr/bin/env python3
"""Initialize database with migrations.

This script checks if the database has been initialized and runs
Alembic migrations if needed.
"""

import subprocess
import sys

from sqlalchemy import create_engine, inspect

from app.core.config import get_settings


def check_database_exists() -> bool:
    """Check if database has any tables.

    Returns:
        bool: True if database has tables, False otherwise
    """
    settings = get_settings()
    engine = create_engine(settings.database.DB_URL)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    engine.dispose()
    return len(tables) > 0


def run_migrations() -> None:
    """Run Alembic migrations to latest version.

    Raises:
        SystemExit: If migration fails
    """
    print("Running database migrations...")
    result = subprocess.run(
        ["alembic", "upgrade", "head"], capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"Migration failed: {result.stderr}")
        sys.exit(1)

    print("Migrations completed successfully")
    print(result.stdout)


def main() -> None:
    """Initialize database if needed."""
    if check_database_exists():
        print("Database already initialized")
        print("To apply new migrations, run: alembic upgrade head")
        return

    print("Initializing database...")
    run_migrations()
    print("Database initialization complete")


if __name__ == "__main__":
    main()
