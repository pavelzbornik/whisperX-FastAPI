# Database Migrations - Quick Reference

## For Developers

### First Time Setup

```bash
# Clone repo and install dependencies
git clone <repo>
cd whisperX-FastAPI
uv sync --all-extras

# Initialize database
uv run python scripts/init_db.py
```

### Daily Workflow

#### Pull Latest Changes

```bash
git pull
uv run alembic upgrade head  # Apply any new migrations
```

#### Make Schema Changes

```bash
# 1. Edit models
vim app/infrastructure/database/models.py

# 2. Create migration
export DB_URL=sqlite:///records.db
./scripts/create_migration.sh "Add feature X"

# 3. Test
./scripts/upgrade_db.sh
uv run pytest

# 4. Commit
git add alembic/versions/*.py app/infrastructure/database/models.py
git commit -m "Add feature X to database"
git push
```

## For DevOps

### New Environment Setup

```bash
# Run migrations
export DB_URL=<production_db_url>
uv run alembic upgrade head
```

### Checking Status

```bash
# Current version
uv run alembic current

# Pending migrations
uv run alembic history --verbose
```

### Production Deployment

```bash
# ALWAYS backup first
pg_dump database > backup.sql  # or appropriate backup command

# Run migrations
uv run alembic upgrade head

# Verify
uv run alembic current
curl http://localhost:8000/health/ready
```

### Rollback (Emergency)

```bash
# Rollback one version
./scripts/downgrade_db.sh -1

# Or restore from backup
psql database < backup.sql
```

## Docker

### Development

```bash
docker-compose up -d  # Migrations run automatically
```

### Production

```bash
docker run -d \
  -e DB_URL=postgresql://user:pass@db/prod \
  -p 8000:8000 \
  whisperx-fastapi
# Migrations run on startup
```

## Common Commands

| Task | Command |
|------|---------|
| Initialize DB | `uv run python scripts/init_db.py` |
| Create migration | `./scripts/create_migration.sh "description"` |
| Apply migrations | `./scripts/upgrade_db.sh` |
| Rollback | `./scripts/downgrade_db.sh -1` |
| Check status | `uv run alembic current` |
| View history | `uv run alembic history` |
| Run tests | `uv run pytest` |

## Troubleshooting

### "Target database is not up to date"

```bash
uv run alembic stamp head
```

### "Can't locate revision"

```bash
# Check available migrations
ls alembic/versions/
# Verify in git
git log alembic/versions/
```

### Migration fails in CI

- Ensure DB_URL is set in environment
- Check migration logs in CI artifacts
- Test locally with same database type

## Help

- [Quick Start](./README.md)
- [Full Documentation](./migrations.md)
- [GitHub Issues](https://github.com/pavelzbornik/whisperX-FastAPI/issues)
