---
name: Copilot Story Document
description: Template for AI-assisted story development and tracking
title: "Story [NUM]: [TITLE]"
labels: ["story", "copilot"]
---

<!-- Powered by BMAD™ Core -->

---

## Story

**As a** [role],
**I want** [action],
**so that** [benefit]

---

## Acceptance Criteria

1. [ ] Criterion 1
2. [ ] Criterion 2
3. [ ] Criterion 3

---

## Tasks / Subtasks

- [ ] Task 1 (AC: # if applicable)
  - [ ] Subtask 1.1
  - [ ] Subtask 1.2
- [ ] Task 2 (AC: # if applicable)
  - [ ] Subtask 2.1
  - [ ] Subtask 2.2
- [ ] Task 3 (AC: # if applicable)
  - [ ] Subtask 3.1
  - [ ] Subtask 3.2

---

## Dev Notes

### Context & Architecture

<!-- Information pulled from docs/ folder and relevant artifacts:
- Relevant source tree info
- Important notes from previous related stories
- Architecture decisions that apply to this story
- Do NOT invent information; only reference actual artifacts
-->

### Testing Standards

**Test File Location:**

- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- E2E tests: `tests/e2e/`

**Testing Requirements:**

- Minimum coverage threshold: 80%
- Framework: pytest with pytest-cov
- Use provided fixtures from `tests/conftest.py`
- Follow Repository Pattern for data access
- Mock external dependencies (WhisperX, HuggingFace)

**Testing Patterns:**

- Domain entities tested independently
- Repository implementations tested with in-memory SQLite
- Services tested with mocked dependencies
- API endpoints tested with TestClient

### Test-Driven Development (TDD) Guidance

This project encourages TDD for feature development where feasible. The following guidance and checklist help keep stories aligned with a test-first approach.

- TDD Flow (three-step cycle):
  1. Red — write a failing test that expresses the desired behavior.

 2. Green — implement the minimal code to make the test pass.
 3. Refactor — clean up code while keeping tests passing.

- Test-First Requirements for Stories:
  - The story should include at least one explicit test goal (what to assert).
  - Tests must be written before production code for new behavior (or a clear TODO pointing to the test if infrastructure is needed first).
  - Tests should be small, deterministic, and fast. Prefer unit tests for business logic.

- Example TDD Cycle (for a small story):
  1. Add a unit test in `tests/unit/` describing the expected domain behavior.

 2. Run the test suite to see it fail.
 3. Implement the minimal change in the domain/service layer.
 4. Run tests and confirm they pass.
 5. Refactor code, run tests again.

- TDD Checklist (to include in the story when applicable):
  - [ ] Tests added for the new behavior (unit/integration as appropriate)
  - [ ] Tests fail before the implementation is added
  - [ ] Tests pass after the minimal implementation
  - [ ] Code refactored and tests still pass
  - [ ] New tests are added to CI and included in coverage measurement

- When to use TDD:
  - Use for new domain logic, algorithmic behavior, and critical business rules.
  - For large integration work (external infra, heavy ML dependencies), create a small unit-testable slice first, or add an explicit testing plan in the story.

**Notes:** When a story explicitly requires TDD, mark the story with a task in the "Tasks / Subtasks" section that describes the tests to add and reference the TDD checklist above.

---
