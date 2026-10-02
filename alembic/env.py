"""Alembic migration environment.

The database connection comes from the application's own ``sync_engine`` rather
than from ``alembic.ini``, so migrations can never run against a different
database (or a different driver) than the app itself uses. Alembic's runner is
synchronous, which is why the sync engine is the right one here.
"""

from logging.config import fileConfig

from alembic import context

from app.infrastructure.database.connection import sync_engine
from app.infrastructure.database.models import Base

config = context.config

# Only configure logging when alembic is driven from the command line. When the
# application calls into alembic at startup, fileConfig would tear down the
# handlers the application logging config has just installed.
if config.config_file_name is not None and config.attributes.get("connection") is None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ``render_as_batch`` makes column alterations work on SQLite, which cannot
# ALTER in place; it is a no-op on backends with native ALTER support.
_COMMON_OPTIONS = {
    "target_metadata": target_metadata,
    "render_as_batch": True,
}


def run_migrations_offline() -> None:
    """Emit migration SQL without connecting to a database."""
    context.configure(
        url=sync_engine.url.render_as_string(hide_password=False),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_COMMON_OPTIONS,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection.

    Callers — the application at startup, and the tests — may supply an open
    connection via ``config.attributes["connection"]``. Otherwise one is opened
    from the application's sync engine.
    """
    existing = config.attributes.get("connection")

    if existing is not None:
        context.configure(connection=existing, **_COMMON_OPTIONS)
        with context.begin_transaction():
            context.run_migrations()
        return

    with sync_engine.connect() as connection:
        context.configure(connection=connection, **_COMMON_OPTIONS)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
