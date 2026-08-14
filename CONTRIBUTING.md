# Contributing to RelayForge

RelayForge favors small, reviewable changes with tests that demonstrate behavior. A contribution should leave the
repository easier to understand than it was before.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pre-commit install
```

On Windows PowerShell, activate with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Use Docker Compose for PostgreSQL and Redis when working on integration behavior.

## Before opening a pull request

Run:

```bash
ruff check src tests
ruff format --check src tests
mypy src/relayforge
pytest
```

For changes touching PostgreSQL, Redis, authentication flow, or HTTP routing, also run integration tests against a
local dependency stack.

## Commit discipline

Prefer commits that represent one coherent engineering change. Good examples:

```text
feat: validate workflow dependency cycles
feat: add redis execution idempotency
fix: reject mixed public-private DNS answers in SSRF guard
test: cover workflow timeout failure state
docs: document durable execution tradeoffs
```

Avoid commits that mix unrelated formatting, dependency updates, feature work, and refactors. If a feature needs a
refactor, either make the refactor independently safe first or keep the change narrowly scoped and explain why the
pieces are inseparable.

Do not manufacture history, backdate commits, or split one generated bulk change into meaningless micro-commits.
History should reflect actual development work.

## Pull request expectations

A useful pull request description answers:

- What behavior changes?
- Why is the change needed?
- What are the security or tenancy implications?
- How was it tested?
- Does it require a migration or configuration change?
- Is rollback safe?

Screenshots are generally irrelevant for this backend unless documentation UI behavior changes. Prefer API
examples, logs with secrets removed, or test output when evidence is useful.

## Architecture rules

### Keep domain code framework-independent

Modules under `relayforge.domain` and the orchestration core should not import FastAPI or SQLAlchemy. If a new use
case requires persistence, define the smallest useful protocol in the application layer and implement it in
infrastructure.

### Keep routes thin

A route should validate HTTP input, obtain dependencies, call an application service, and serialize output. It
should not contain graph traversal, password algorithms, raw SQL, or complex authorization rules.

### Tenant scope is mandatory

Any query for organization-owned data must include the organization boundary. A repository method that fetches a
workflow by ID without organization context is a security bug unless it is explicitly an administrative internal
operation with separate controls.

### Do not add arbitrary workflow evaluation

Do not introduce `eval`, `exec`, shell execution, unrestricted Jinja expressions, or dynamic Python import as a
workflow feature. Custom code requires an isolated sandbox architecture and a separate security review.

### Preserve deterministic execution

Changes to graph scheduling must preserve deterministic dependency semantics. Parallelism may change completion
order but must not change which dependencies are required or silently ignore failures.

## Testing rules

- Add a test for new behavior.
- Add a regression test for each bug fix.
- Prefer unit tests for pure logic.
- Use integration tests when the contract depends on real database/Redis behavior.
- Do not mock the exact implementation under test so heavily that the test can no longer fail meaningfully.
- Do not lower assertions or coverage thresholds simply to make CI green.
- Keep tests deterministic and independent of public internet services.

## Security review triggers

Explicitly call out changes involving:

- authentication or token claims,
- organization membership/RBAC,
- secrets or encryption,
- outbound HTTP/network policy,
- webhook verification,
- API keys,
- SQL query scoping,
- deserialization,
- logging of user-controlled data,
- dependency or build-chain changes.

Review `docs/threat-model.md` when touching these areas.

## Database migrations

Schema changes require an Alembic migration. Do not rewrite a migration that may have been deployed. Prefer
expand/contract changes for production compatibility.

Migration changes should include a downgrade when it is safe and meaningful. If downgrade would destroy or
fabricate data, document that limitation rather than pretending rollback is safe.

## Documentation

Update documentation in the same change when behavior, configuration, API shape, security assumptions, or
operational procedures change. Architecture decisions that would otherwise be repeatedly debated should receive
an ADR under `docs/adr`.

## Dependency changes

Explain why a new runtime dependency is needed. Prefer the standard library or an existing dependency when it can
solve the problem clearly and safely. New security-sensitive dependencies should be checked for maintenance status,
license compatibility, and known vulnerabilities.

## Style

Ruff is authoritative for lint/format conventions and mypy is authoritative for static type checks. Do not add
large blocks of comments that restate obvious code. Comments should explain constraints, tradeoffs, or non-obvious
reasoning.
