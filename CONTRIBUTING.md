# Contributing to whisperX-FastAPI

Thank you for your interest in contributing to whisperX-FastAPI! We welcome contributions of all kinds, including bug fixes, new features, documentation improvements, and more.

## Branch Strategy

```text
feature/xxx  →  dev  →  main
fix/xxx      ↗
```

- All development happens in feature branches targeting `dev`
- `dev` is the default branch — pull requests target it automatically
- `main` receives periodic releases from `dev` and is always production-ready

## Getting Started

1. **Fork the repository** and clone it to your local machine.
2. **Set up your development environment** as described in the [README.md](README.md).
3. **Install pre-commit hooks** to ensure code quality:

   ```sh
   pip install pre-commit
   pre-commit install
   ```

   This automatically runs on every commit:
   - Format and lint with Ruff
   - Type checking with mypy
   - Common issue checks (trailing whitespace, large files, etc.)
   - README badge updates from `pyproject.toml`

## Workflow

### Starting a new feature or fix

```sh
git checkout dev && git pull
git checkout -b feat/my-thing   # or fix/my-thing
```

### Opening a pull request

```sh
gh pr create --fill --draft     # opens a draft PR to dev immediately
```

`--fill` uses your commit messages as the title and body — no manual writing needed if your commits are descriptive.

### Merging

```sh
gh pr ready                     # mark out of draft when done
gh pr merge --squash --auto     # auto-merges when CI goes green
```

Feature branches are deleted automatically after merge.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) — the pre-commit hook enforces this via commitizen:

```text
feat: add PostgreSQL support
fix: handle missing HF_TOKEN gracefully
chore: bump ruff to 0.15.2
docs: update contributing guide
```

## Code Style & Quality

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) and use type hints throughout.
- Keep functions and classes small and focused.
- Add or update docstrings for public functions and classes.
- Code must pass [Ruff](https://docs.astral.sh/ruff/) checks: `uv run ruff check .` and `uv run ruff format --check .`
- Code coverage must be at least **80%**.

### Running tests

```sh
# All tests with coverage (CI standard)
uv run pytest --cov=app --cov-report=term --cov-fail-under=80

# Fast subset (unit + integration, no slow/load)
uv run pytest -m "not slow and not load"

# Single file
uv run pytest tests/unit/domain/entities/test_task.py

# Load tests (run manually, not in CI)
uv run pytest -m load
```

### Badge updates

Badges in README are updated automatically when you commit changes to `pyproject.toml`. To update manually:

```sh
uv run python scripts/update-badges.py
uv run python scripts/update-badges.py --dry-run  # preview only
```

## Pull Request Guidelines

- PRs must target the `dev` branch (the default).
- Include a clear description of your changes and the motivation.
- Reference related issues (e.g., `Fixes #123`).
- All CI checks must pass:
  - Ruff linter and formatter
  - mypy type checking
  - All tests pass with ≥80% coverage
  - Dependency review (no new high/critical vulnerabilities)

## Reporting Issues

If you find a bug or have a feature request, please [open an issue](https://github.com/pavelzbornik/whisperX-FastAPI/issues) with as much detail as possible.
