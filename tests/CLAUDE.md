# tests/CLAUDE.md

Test organization, fixtures, mocks, factories, and coverage requirements.

## Markers

Tests are tagged with pytest markers — `--strict-markers` is enforced:

| Marker | Description |
| --- | --- |
| `unit` | All deps mocked; no DB, no network, no GPU. Fast. |
| `integration` | Real DB or service integration. |
| `e2e` | Full API via `TestClient`. |
| `slow` | ML operations (model load, inference). |

Run a subset: `uv run pytest -m unit` or `uv run pytest -m "not slow"`.

## TestContainer (`fixtures/test_container.py`)

Overrides production ML services with fast, deterministic mock implementations. Use the
`test_container` fixture in any test that exercises code paths involving ML services.
The TestContainer wires the same `dependency-injector` container structure so DI behavior
is preserved.

## Mocks (`mocks/`)

`MockTranscriptionService`, `MockAlignmentService`, `MockDiarizationService`,
`MockSpeakerAssignmentService`. Return hardcoded, deterministic data — never touch GPU,
disk (beyond fixtures), or network. If you need a different fixture output, extend the
mock rather than adding conditional logic.

## Factories (`factories/task_factory.py`)

factory-boy `TaskFactory` builds `Task` domain entities with sensible defaults. Prefer
factories over inline `Task(...)` construction in tests — factories stay in sync when the
entity signature changes.

## DB & Env Fixture (`conftest.py`)

Session-scoped setup sets:

- `DB_URL=sqlite:///<tmp_path>`
- `DEVICE=cpu`, `COMPUTE_TYPE=int8`
- `WHISPER_MODEL=tiny`

Tables are auto-created before the test session and dropped after. Do not override these
env vars inside individual tests unless the test specifically exercises that path.

## Coverage

≥80% required. Run: `uv run pytest --cov=app --cov-report=term --cov-fail-under=80`.
CI will fail the `test` job if coverage drops below the threshold.
