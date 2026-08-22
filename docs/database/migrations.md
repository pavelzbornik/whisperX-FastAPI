# Database migrations

The schema is versioned with [Alembic](https://alembic.sqlalchemy.org/). Revisions live in
`alembic/versions/`; `alembic/env.py` takes its connection from the application's own
`sync_engine`, so migrations always target the database named by `DB_URL`.

## Applying migrations

The application applies pending migrations itself during startup, so a fresh deployment
needs no extra step — `task run` or `docker compose up` is enough.

To drive them by hand:

```bash
task db:upgrade      # apply all pending migrations
task db:current      # show the revision the database is at
task db:downgrade    # revert the most recent migration
```

## Adding a migration

After changing `app/infrastructure/database/models.py`:

```bash
task db:revision MSG="add retry_count to tasks"
```

Then **read the generated file before committing it**. Autogenerate compares model metadata
against the live database and does not detect everything — a column rename in particular is
emitted as a drop plus an add, which silently discards the data. Rewrite those by hand using
`op.alter_column(..., new_column_name=...)`.

Verify the result round-trips:

```bash
task db:upgrade && task db:downgrade && task db:upgrade
uv run alembic check          # passes when models and migrations agree
```

`alembic check` is the quickest way to catch a model change that never got a migration.

## Upgrading a database that predates Alembic

Databases created by the old `Base.metadata.create_all` startup path hold the right tables
but carry no `alembic_version` row, so a plain `upgrade head` would fail with "table already
exists". Startup detects this and stamps such a database **at head**, then stops.

Head is the correct mark because `create_all` built that schema from the models as they
are now, and head is precisely what the current models describe — the same statement
`alembic check` makes. Stamping any earlier revision would replay later migrations against
columns that already exist, which fails with "duplicate column name". No manual
intervention is needed, and existing rows are left untouched.

## Multi-worker deployments

Migrations run once per process at startup. The shipped container runs a single Gunicorn
worker, so this is a single execution. If you raise the worker count, every worker will
attempt the upgrade concurrently; run `task db:upgrade` as a separate deploy step before
starting the app rather than relying on startup in that setup.
