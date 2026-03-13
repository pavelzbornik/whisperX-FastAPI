# docs

Documentation structure and when to update it.

## Architecture Decision Records (`architecture/`)

ADRs document *why* core design decisions were made:

| File | Topic |
| --- | --- |
| `async-sqlalchemy-concurrency.md` | Async SQLAlchemy migration: dual-engine design, load test results |
| `dependency-injection.md` | DI Container design and rationale |
| `domain-model-pattern.md` | Pure domain entity and Repository pattern |
| `exception-handling.md` | Typed exception hierarchy strategy |
| `ml-service-abstraction.md` | WhisperX abstraction behind service interfaces |

**When to update:** Add or update an ADR whenever a new architectural pattern is adopted
or an existing one is significantly changed. Keep ADRs concise — decision, context,
consequences. Do not rewrite history; append a superseding ADR instead.

## Implementation Stories (`stories/`)

Ordered stories (1.x → 2.x → 3.x → 4.x) document the evolutionary path from the
original simple architecture to the current layered design. Read these for context on
*why* things are structured as they are.

**Do not modify stories.** They are historical records, not living documentation.

## Configuration Migration (`CONFIGURATION_MIGRATION.md`)

Step-by-step guide for migrating code from the legacy `Config` class to `get_settings()`.
Consult this before touching any code that still references `Config`.

## Keeping Docs Current

- `architecture/` ADRs: update when patterns change.
- `stories/`: read-only historical record.
- `CONFIGURATION_MIGRATION.md`: update if `get_settings()` API changes.
- This `CLAUDE.md`: update if the docs folder structure changes.
