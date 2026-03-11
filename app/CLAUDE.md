# app

Code standards that apply across all `app/` subfolders.

## Type Annotations

Use Python 3.10+ union syntax throughout:

- `str | None` not `Optional[str]`
- `dict[str, Any]`, `list[str]` not `Dict`, `List`
- `collections.abc.Generator` / `collections.abc.Callable` — never `typing.Generator` / `typing.Callable`

For untyped third-party APIs (whisperx, torch, numpy), add `# type: ignore[attr-defined]` on the offending line.

## Static Analysis

All code must pass with zero errors/warnings:

```bash
uv run mypy app/        # disallow_untyped_defs = true; must show "Success: no issues found"
uv run ruff check .     # replaces flake8 + isort
uv run ruff format .    # replaces black
```

Ruff is the single formatter/linter — never run flake8, isort, or black directly.

## Docstrings

pydocstyle is enforced via pre-commit. Every public function, method, and class needs a
PEP 257-compliant docstring. One-liners are fine for simple functions:

```python
def get_task_id(self) -> str:
    """Return the task's unique identifier."""
```

## Settings

`get_settings()` returns a cached `Settings` singleton (pydantic-settings). Use it for all
new code. The legacy `Config` class in `app/core/config.py` is **deprecated** — do not
reference it in new code. See `docs/CONFIGURATION_MIGRATION.md` for migration guidance.

## Pre-commit

Running `uv run pre-commit run --all-files` executes: mypy, ruff, yamllint, hadolint,
shellcheck, codespell, pydocstyle, and gitleaks. All must pass before a PR is opened.
