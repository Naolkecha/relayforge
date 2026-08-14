# Testing strategy

## Philosophy

RelayForge tests behavior at the narrowest useful layer. Graph algorithms, retry semantics, security policy, and
execution state are unit-tested without external services. PostgreSQL/Redis integration tests are reserved for
contracts that cannot be meaningfully proven with mocks.

A test should protect a behavior that matters. Tests created only to inflate coverage are discouraged.

## Test layers

### Domain and execution unit tests

These tests cover:

- deterministic topological ordering,
- unknown dependency rejection,
- cycle detection,
- retry delay calculations,
- execution state transitions,
- path resolution and invalid paths,
- condition operators,
- HTTP executor response handling,
- retry exhaustion,
- timeout failure,
- duplicate-request idempotency,
- execution serialization.

They are fast and do not require Docker.

### Security unit tests

Security tests cover:

- Argon2 verification and malformed hashes,
- JWT kind/signature validation,
- API-key one-way hashing,
- Fernet round trips and authentication failure,
- webhook body/timestamp signatures,
- replay-window rejection,
- SSRF policy across IPv4 and IPv6 private/special ranges,
- host allowlisting,
- credential-bearing URL rejection.

When a security bug is fixed, a regression test should reproduce the original bypass.

### Application-service tests

In-memory/fake ports verify orchestration behavior such as audit event creation and cross-tenant resource lookup
without binding those tests to SQLAlchemy internals.

### Integration tests

The GitHub Actions integration job provisions PostgreSQL and Redis, applies Alembic migrations, then exercises:

- liveness/readiness,
- registration,
- JWT-protected workflow creation,
- PostgreSQL workflow persistence,
- workflow execution,
- Redis-backed idempotent replay.

These tests are marked `integration` and are excluded from the default local unit run unless selected explicitly.

## Commands

Default quality suite:

```bash
pytest
```

Unit-only:

```bash
pytest tests/unit
```

Integration stack:

```bash
pytest -m integration --no-cov
```

Inspect slow tests:

```bash
pytest --durations=20
```

Run one regression:

```bash
pytest tests/unit/test_ssrf.py -k private -vv
```

## Coverage policy

The repository-wide floor starts at 60% because adapters are intentionally less covered than the high-risk core.
The first measured baseline in the local build is approximately 64% total with substantially higher coverage in
workflow/security modules.

Coverage is a floor, not the goal. The progression target is:

1. 60%: current enforced baseline,
2. 70%: add API dependency/middleware and repository adapter tests,
3. 80%: add auth service, SQLAlchemy repositories, Redis adapters, and negative integration cases,
4. maintain or raise the floor when features are added.

A pull request that adds many uncovered lines must either add relevant tests or explain why those lines are not
practically testable.

## Regression-test standard

A bug fix should usually follow:

1. write a test that fails for the reported behavior,
2. make the smallest coherent implementation fix,
3. run the focused test,
4. run the full suite,
5. run lint/type checks,
6. keep the regression test in the repository.

Do not weaken assertions just because an implementation is difficult to satisfy.

## Determinism

Unit tests should not depend on:

- live internet services,
- wall-clock sleeping where a fake sleep can be injected,
- unordered dictionary/set output when order matters,
- developer-specific environment variables,
- production credentials.

The engine injects sleep behavior partly to make retry timing deterministic in tests.

## Integration data isolation

Integration tests must use a dedicated database and Redis logical database. Never point integration tests at a
production database. Test data may be unique per run when parallelization is introduced.

## What CI proves

The quality job proves from a clean runner that the package installs, lint passes, formatting is canonical, types
check, and unit tests meet the coverage floor.

The integration job proves migrations apply and the real service stack handles a complete authenticated workflow.

The security job independently audits known dependency vulnerabilities and source-level security patterns.
