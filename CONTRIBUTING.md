# Contributing to whisperX-FastAPI

Thank you for your interest in contributing to whisperX-FastAPI! We welcome contributions of all kinds, including bug fixes, new features, documentation improvements, and more.

## Getting Started

1. **Fork the repository** and clone it to your local machine.
2. **Set up your development environment** as described in the [README.md](README.md).
3. **Install pre-commit hooks** to ensure code quality and automatic updates:

   ```sh
   # Install pre-commit (if not already installed)
   pip install pre-commit

   # Install the git hooks
   pre-commit install
   ```

   This will automatically:
   - Format and lint your code with Ruff
   - Run type checking with mypy
   - Check for common issues (trailing whitespace, large files, etc.)
   - **Update README badges** to reflect current versions from your environment

4. **Create a new branch** for your feature or bugfix:

   ```sh
   git checkout -b my-feature-branch
   ```

4. **Make your changes** and add tests as appropriate.
5. **Run the test suite** to ensure everything works:

   ```sh
   pytest
   ```

6. **Commit your changes** with a clear and descriptive message.
7. **Push your branch** to your fork and open a Pull Request (PR) against the `dev` branch.

## Code Style & Quality

- Follow [PEP8](https://www.python.org/dev/peps/pep-0008/) for Python code.
- Use type hints where possible.
- Keep functions and classes small and focused.
- Add or update docstrings for public functions and classes.
- Code must pass [Ruff](https://docs.astral.sh/ruff/) linter and formatter checks (`ruff check .` and `ruff format --check .`).
- Code coverage must be at least **55%** (see CI for details).

### Automatic Badge Updates

The repository uses a pre-commit hook to automatically update README badges (Python version, CUDA version, FastAPI version, WhisperX version) from `pyproject.toml`.

- **Badges are updated automatically** when you commit changes to `pyproject.toml` or the badge update script itself.
- The script reads version information directly from `pyproject.toml` as the single source of truth.
- If you need to manually update badges, run:

  ```sh
  python scripts/update-badges.py
  ```

- To see what would be updated without making changes:

  ```sh
  python scripts/update-badges.py --dry-run
  ```

## Pull Request Guidelines

- PRs should be opened against the `dev` branch.
- Include a clear description of your changes and the motivation behind them.
- Reference related issues in your PR description (e.g., `Fixes #123`).
- Ensure all tests pass and new code is covered by tests.
- Code must pass all CI checks:
  - Ruff linter and formatter
  - All tests must pass
  - Coverage must be at least 55%
- If your change affects documentation, update the relevant docs.

## Reporting Issues

If you find a bug or have a feature request, please [open an issue](https://github.com/pavelzbornik/whisperX-FastAPI/issues) and provide as much detail as possible.
