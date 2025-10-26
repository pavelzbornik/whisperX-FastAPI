"""
Migration: Add task queue tracking fields

This migration adds new columns to the tasks table to support
task queue abstraction with retry logic and enhanced status tracking.

New columns:
- retry_count: Number of retry attempts made (default: 0)
- max_retries: Maximum retry attempts allowed (default: 3)
- last_error: Most recent error message from retries
- scheduled_at: When the task was scheduled for execution

Run this migration:
    python -m app.infrastructure.database.migrations.001_add_task_queue_fields
"""

from sqlalchemy import text
from app.infrastructure.database.connection import engine


def upgrade() -> None:
    """Add task queue tracking fields to tasks table."""
    with engine.connect() as conn:
        # Add retry_count column (default 0)
        conn.execute(
            text(
                """
                ALTER TABLE tasks
                ADD COLUMN retry_count INTEGER DEFAULT 0
                """
            )
        )

        # Add max_retries column (default 3)
        conn.execute(
            text(
                """
                ALTER TABLE tasks
                ADD COLUMN max_retries INTEGER DEFAULT 3
                """
            )
        )

        # Add last_error column
        conn.execute(
            text(
                """
                ALTER TABLE tasks
                ADD COLUMN last_error VARCHAR(500)
                """
            )
        )

        # Add scheduled_at column
        conn.execute(
            text(
                """
                ALTER TABLE tasks
                ADD COLUMN scheduled_at DATETIME
                """
            )
        )

        conn.commit()
        print("✓ Migration completed: Added task queue tracking fields")


def downgrade() -> None:
    """Remove task queue tracking fields from tasks table."""
    with engine.connect() as conn:
        # SQLite doesn't support DROP COLUMN directly in older versions
        # For production PostgreSQL/MySQL, you would use:
        # ALTER TABLE tasks DROP COLUMN column_name

        # For SQLite, we need to recreate the table without these columns
        # This is a simplified version - in production use a migration tool
        print("⚠ Downgrade not fully implemented for SQLite")
        print("  Consider using Alembic for production migrations")
        conn.commit()


if __name__ == "__main__":
    print("Running migration: Add task queue tracking fields")
    try:
        upgrade()
        print("✓ Migration successful!")
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        raise
