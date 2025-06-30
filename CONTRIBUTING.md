# Contributing to whisperX-FastAPI

Thank you for your interest in contributing to whisperX-FastAPI! We welcome contributions of all kinds, including bug fixes, new features, documentation improvements, and more.

## Getting Started

1. **Fork the repository** and clone it to your local machine.
2. **Set up your development environment** as described in the [README.md](README.md).
3. **Create a new branch** for your feature or bugfix:

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
