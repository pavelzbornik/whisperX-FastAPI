"""Unit tests for Alembic migration handling at startup."""

from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, inspect, text

from app.infrastructure.database import migrations
from app.infrastructure.database.models import Base


@pytest.fixture
def sqlite_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    """Provide a throwaway file-backed SQLite engine."""
    engine = create_engine(f"sqlite:///{tmp_path / 'migrations.db'}")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def patched_engine(
    monkeypatch: pytest.MonkeyPatch, sqlite_engine: Engine
) -> Generator[Engine, None, None]:
    """Point the migration module at the throwaway engine."""
    monkeypatch.setattr(migrations, "sync_engine", sqlite_engine)
    yield sqlite_engine


def _table_names(engine: Engine) -> set[str]:
    """Return the set of table names present in *engine*'s database."""
    with engine.connect() as connection:
        return set(inspect(connection).get_table_names())


def _current_revision(engine: Engine) -> str | None:
    """Return the Alembic revision the database is stamped at."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _head_revision() -> str | None:
    """Return the head revision defined on disk."""
    config = migrations.Config(str(migrations._ALEMBIC_INI))
    config.set_main_option("script_location", str(migrations._PROJECT_ROOT / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def _make_legacy_database(engine: Engine) -> None:
    """Build a pre-Alembic database: initial schema, no version stamp.

    The base revision is derived from the script directory rather than written
    out, so the tests keep working if the initial revision is ever renamed or
    squashed.
    """
    with engine.begin() as connection:
        config = migrations._build_config(connection)
        base_revision = ScriptDirectory.from_config(config).get_base()
        command.upgrade(config, base_revision)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))


@pytest.mark.unit
def test_migrations_create_schema_on_empty_database(patched_engine: Engine) -> None:
    """A fresh database ends up with every model table and a version stamp."""
    migrations.run_migrations()

    tables = _table_names(patched_engine)
    assert set(Base.metadata.tables) <= tables
    assert "alembic_version" in tables
    assert _current_revision(patched_engine) == _head_revision()


@pytest.mark.unit
def test_migrations_are_idempotent(patched_engine: Engine) -> None:
    """Running migrations twice is a no-op the second time."""
    migrations.run_migrations()
    first = _current_revision(patched_engine)

    migrations.run_migrations()

    assert _current_revision(patched_engine) == first


@pytest.mark.unit
def test_legacy_database_is_stamped_not_recreated(patched_engine: Engine) -> None:
    """A create_all database is adopted rather than failing on existing tables.

    This is the upgrade path for deployments that predate Alembic: the tables
    are already there but unversioned, so `upgrade head` alone would fail.
    """
    # The realistic legacy shape: built by the previous release's create_all,
    # so it matches the initial revision. Reproduced by migrating to that
    # revision and then removing the stamp.
    _make_legacy_database(patched_engine)
    assert "alembic_version" not in _table_names(patched_engine)

    # Prove the data survives: a stamp must not drop or recreate the table.
    with patched_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tasks (uuid, status, task_type, created_at, updated_at) "
                "VALUES ('legacy-1', 'completed', 'transcription', "
                "'2026-01-01 00:00:00', '2026-01-01 00:00:00')"
            )
        )

    migrations.run_migrations()

    assert _current_revision(patched_engine) == _head_revision()
    with patched_engine.connect() as connection:
        rows = connection.execute(
            text("SELECT uuid FROM tasks WHERE uuid = 'legacy-1'")
        ).fetchall()
    assert [row[0] for row in rows] == ["legacy-1"]


@pytest.mark.unit
def test_empty_database_is_not_treated_as_legacy(patched_engine: Engine) -> None:
    """A database with no tables at all takes the normal upgrade path."""
    with patched_engine.connect() as connection:
        assert migrations._is_legacy_database(connection) is False


@pytest.mark.unit
def test_migrated_database_is_not_treated_as_legacy(patched_engine: Engine) -> None:
    """Once stamped, a database is no longer considered legacy."""
    migrations.run_migrations()

    with patched_engine.connect() as connection:
        assert migrations._is_legacy_database(connection) is False


@pytest.mark.unit
def test_missing_alembic_config_raises(
    monkeypatch: pytest.MonkeyPatch, patched_engine: Engine, tmp_path: Path
) -> None:
    """A missing alembic.ini fails loudly rather than silently skipping."""
    monkeypatch.setattr(migrations, "_ALEMBIC_INI", tmp_path / "nope.ini")

    with pytest.raises(FileNotFoundError):
        migrations.run_migrations()


@pytest.mark.unit
def test_downgrade_removes_model_tables(patched_engine: Engine) -> None:
    """The initial revision's downgrade is implemented, not a stub."""
    migrations.run_migrations()

    with patched_engine.begin() as connection:
        config = migrations._build_config(connection)
        command.downgrade(config, "base")

    remaining = _table_names(patched_engine)
    assert not (set(Base.metadata.tables) & remaining)


@pytest.mark.unit
def test_partial_legacy_schema_is_refused(patched_engine: Engine) -> None:
    """An incomplete unversioned schema fails loudly instead of being stamped.

    A database holding only some application tables is not a legacy database
    but a broken one — an interrupted deployment, or a partial restore.
    Stamping it would record migrations as applied that never ran, leaving the
    missing tables to fail at runtime instead of at startup.
    """
    migrations.run_migrations()
    with patched_engine.begin() as connection:
        connection.execute(text("DROP TABLE speaker_embeddings"))
        connection.execute(text("DROP TABLE alembic_version"))

    with pytest.raises(RuntimeError, match="speaker_embeddings"):
        migrations.run_migrations()


@pytest.mark.unit
def test_legacy_database_gains_columns_added_by_later_revisions(
    patched_engine: Engine,
) -> None:
    """A pre-Alembic database is brought all the way up to head.

    This is the real upgrade path: the database was built by `create_all` from
    the previous release, so it predates every column added since. Stamping it
    at the initial revision and then upgrading is what applies those columns.
    Stamping it at head instead would mark the migrations as already applied
    and silently leave the table missing `retry_count`.
    """
    # Build the schema as the initial revision left it — i.e. without any
    # column added by a later revision — and strip the version stamp so the
    # database looks pre-Alembic.
    _make_legacy_database(patched_engine)

    columns = {c["name"] for c in inspect(patched_engine).get_columns("tasks")}
    assert "retry_count" not in columns, "precondition: column not yet present"

    migrations.run_migrations()

    columns = {c["name"] for c in inspect(patched_engine).get_columns("tasks")}
    assert "retry_count" in columns
    assert _current_revision(patched_engine) == _head_revision()
