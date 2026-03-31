---
name: coverage-check
description: Check test coverage and identify files below 80% threshold. Use before committing to avoid SonarCloud failures.
user_invocable: true
---

# Coverage Check

Run the test suite with coverage reporting and identify gaps.

## Steps

1. Run: `uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80`
2. Parse the output to find files below 80% coverage
3. For each file below threshold, list the uncovered line ranges
4. Summarize: total coverage, files below 80%, and which code paths need tests
5. If coverage is below 80%, suggest specific test cases to write

Report the results concisely. Do not write tests unless asked — just identify the gaps.
