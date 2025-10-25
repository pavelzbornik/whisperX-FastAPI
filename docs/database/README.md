# Database Migrations with Alembic

This document describes how to use Alembic for managing database schema changes in the WhisperX FastAPI application.

## Overview

This project uses [Alembic](https://alembic.sqlalchemy.org/) for database migrations instead of raw SQLAlchemy `create_all()`. This provides:

- **Versioned schema changes**: Each change is tracked in git
- **Rollback capability**: Can revert schema changes safely
- **Production safety**: Test migrations before applying to production
- **Team coordination**: Everyone applies the same schema changes
- **Data migration**: Can transform data during schema updates

## Quick Start

### Initialize Database (First Time)

```bash
# Using Python script (recommended)
uv run python scripts/init_db.py

# Or directly with Alembic
uv run alembic upgrade head
```

### Create a Migration

```bash
export DB_URL=sqlite:///records.db
./scripts/create_migration.sh "Add new column"
```

### Apply Migrations

```bash
./scripts/upgrade_db.sh
```

### Rollback Migrations

```bash
./scripts/downgrade_db.sh -1  # Rollback one version
```

## Common Operations

### Check Migration Status

```bash
# Show current version
uv run alembic current

# Show migration history
uv run alembic history

# Show pending migrations
uv run alembic show head
```

## Development Workflow

1. **Modify Models**: Update `app/infrastructure/database/models.py`
2. **Create Migration**: `./scripts/create_migration.sh "description"`
3. **Review Generated Migration**: Check `alembic/versions/`
4. **Test**: `uv run alembic upgrade head && uv run pytest`
5. **Commit**: Add migration file to git

## Production Deployment

1. **Backup Database**: Always backup before migration
2. **Apply Migrations**: `uv run alembic upgrade head`
3. **Verify**: Check application health endpoints
4. **Rollback if Needed**: `uv run alembic downgrade -1`

## Docker

The Docker container automatically runs migrations on startup:

```bash
docker run -d -p 8000:8000 -e DB_URL=sqlite:///records.db whisperx-fastapi
```

## Testing

Tests automatically use Alembic migrations for schema setup:

```bash
uv run pytest  # Migrations run automatically
```

## Troubleshooting

### Migration Fails

```bash
# Check current version
uv run alembic current

# Stamp to specific version
uv run alembic stamp <revision>
```

### Changes Not Detected

Verify models are imported in `alembic/env.py`:

```python
from app.infrastructure.database.models import Base
target_metadata = Base.metadata
```

## Best Practices

1. **Always review generated migrations** - Autogenerate is not perfect
2. **Test upgrade and downgrade** - Before committing
3. **One migration per feature** - Keep focused
4. **Never edit applied migrations** - Create new migration instead
5. **Backup before production** - Always have rollback plan

## Full Documentation

See [docs/database/migrations.md](./migrations.md) for complete documentation including:

- Advanced data migrations
- Multiple database support
- Detailed troubleshooting
- Migration patterns
- Production deployment strategies
