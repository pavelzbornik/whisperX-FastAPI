"""Applying Alembic migrations to the configured database.

The application owns its schema at startup: it runs any pending migrations
before serving traffic, so a fresh deployment needs no manual setup step.

Databases created by the earlier ``Base.metadata.create_all`` startup path have
the right tables but no ``alembic_version`` row, which would make
``upgrade head`` fail on "table already exists". Those are detected and stamped
at the initial revision — safe because that revision produces DDL identical to
what ``create_all`` produced — and then upgraded normally.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, inspect

from app.infrastructure.database.connection import sync_engine
from app.infrastructure.database.models import Base

logger = logging.getLogger(__name__)

# app/infrastructure/database/migrations.py -> repository root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _PROJECT_ROOT / "alembic.ini"


def _build_config(connection: Connection) -> Config:
    """Build an Alembic config bound to an already-open connection.

    Args:
        connection: Open SQLAlchemy connection for migrations to run on.

    Returns:
        Alembic ``Config`` whose environment will reuse *connection*.
    """
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_PROJECT_ROOT / "alembic"))
    # Consumed by alembic/env.py so it does not open a second connection and
    # does not reconfigure application logging.
    config.attributes["connection"] = connection
    return config


def _is_legacy_database(connection: Connection) -> bool:
    """Report whether this database predates Alembic.

    A legacy database is one created by the old ``create_all`` startup path: it
    already holds application tables but has no Alembic version stamp.

    Args:
        connection: Open SQLAlchemy connection to inspect.

    Returns:
        ``True`` when the schema exists but is unversioned.
    """
    if MigrationContext.configure(connection).get_current_revision() is not None:
        return False

    existing = set(inspect(connection).get_table_names())
    return bool(existing & set(Base.metadata.tables))


def run_migrations() -> None:
    """Bring the database schema up to the latest revision.

    Blocking and synchronous — call it from a worker thread when running inside
    the event loop.
    """
    if not _ALEMBIC_INI.is_file():
        raise FileNotFoundError(f"Alembic config not found at {_ALEMBIC_INI}")

    # begin() rather than connect(): when alembic is handed an existing
    # connection it leaves the transaction to the caller, so a plain connect()
    # would roll the DDL back when the block exits.
    with sync_engine.begin() as connection:
        config = _build_config(connection)

        base_revision = ScriptDirectory.from_config(config).get_base()

        if base_revision is not None and _is_legacy_database(connection):
            logger.info(
                "Existing unversioned schema detected; stamping it as revision "
                "%s before upgrading",
                base_revision,
            )
            # Stamped at the *initial* revision rather than at head: the legacy
            # schema matches that revision, so any later revisions still need to
            # be applied by the upgrade below.
            command.stamp(config, base_revision)

        command.upgrade(config, "head")
