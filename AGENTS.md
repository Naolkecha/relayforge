# RelayForge agent instructions

These instructions apply to coding agents working in this repository.

## Required checks

Before declaring an implementation task complete, run:

```bash
ruff check src tests
ruff format --check src tests
mypy src/relayforge
pytest
```

Run integration tests for changes that depend on PostgreSQL, Redis, FastAPI lifespan behavior, migrations, or
SQLAlchemy repositories.

## Architecture

- Domain and execution logic must not depend on FastAPI.
- Route handlers stay thin.
- Persistence details stay under `infra`.
- Organization-owned queries must enforce organization scope.
- Workflow expressions must never use arbitrary Python evaluation.
- Outbound user-controlled URLs must pass SSRF policy.

## Tests

- Add meaningful behavior tests with features.
- Add regression tests with bug fixes.
- Do not remove or weaken tests just to make a patch pass.
- Keep unit tests independent of live public services.

## Security

Never write credentials into source, fixtures, logs, or documentation. Use generated test values that cannot be
mistaken for production credentials. Never add `eval`, `exec`, shell execution, or unsafe deserialization to
workflow paths.

## Change quality

Avoid filler modules, dead code, duplicated implementations, and giant files. Prefer cohesive components with
clear responsibilities. Explain non-obvious tradeoffs in docs or an ADR rather than adding speculative abstractions.
