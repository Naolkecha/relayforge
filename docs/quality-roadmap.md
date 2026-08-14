# Quality roadmap

This file records measurable engineering follow-ups rather than presenting the initial repository as finished.

## Current baseline

- Unit tests: 92 passing in the initial local verification environment.
- Repository coverage: approximately 64% with branch coverage enabled.
- Core workflow/security modules: materially higher than the repository aggregate.
- Unit test runtime: a few seconds on the initial development environment.
- Docker/CI definitions: present; full container execution must be verified on a machine with Docker/network access.

## Next measurable targets

### Coverage to 70%

Add direct tests for:

- API request middleware,
- dependency role enforcement,
- error envelopes,
- Redis queue/idempotency adapter behavior,
- database session rollback semantics.

### Coverage to 80%

Add integration and adapter tests for:

- registration conflicts and login failures,
- refresh after membership removal,
- workflow repository version updates,
- cross-tenant HTTP behavior,
- readiness dependency failures,
- migration upgrade from an empty database.

Only raise `--cov-fail-under` after the measured suite stays above the new threshold with margin.

### Durable execution

Persist execution and step attempts before introducing asynchronous workers. Add lease ownership, heartbeat,
cancellation, and recovery tests before claiming at-least-once/at-most-once semantics.

### Reproducible dependency lock

Choose and commit a deployment lock strategy, for example `uv.lock`, and make CI verify it is synchronized with
`pyproject.toml`. Do not commit a lockfile generated without actually resolving dependencies.

### Release discipline

After the first stable milestone:

- create signed/annotated release tags,
- publish release notes derived from the changelog,
- maintain actual development history through focused feature/test commits,
- avoid bulk generated commits that obscure reviewable work.
