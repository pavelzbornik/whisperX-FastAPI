---
name: pr-ready
description: Validate code quality, run tests, check coverage, and create a PR when all checks pass. Use when ready to submit work.
user_invocable: true
---

# PR Ready

Prepare and validate a pull request. Only create the PR when all checks pass.

## Steps

1. **Lint and format**: Run `task check` (ruff check + ruff format + mypy). Fix any issues found.
2. **Run tests**: Run `task test` (full suite with ≥80% coverage gate). If tests fail, diagnose and fix.
3. **Coverage on new code**: Run `uv run pytest --cov=app --cov-report=term-missing` and check that files changed on this branch have >80% coverage. If not, write tests for uncovered paths.
4. **Review diff**: Run `git diff $(git merge-base HEAD dev)...HEAD --stat` to summarize changes. Flag anything that looks unintentional.
5. **Create PR**: Only when steps 1-4 pass, commit any remaining changes and create the PR with `gh pr create` targeting `dev`. Include a structured description with summary, test plan, and coverage delta.

If any step fails, fix the issue and re-run that step before proceeding. Do not create the PR until everything is green.
