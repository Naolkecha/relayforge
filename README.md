# RelayForge

RelayForge is an API-first workflow orchestration backend for safely composing deterministic data transforms,
conditions, delays, and outbound HTTP actions. It is designed as a production-oriented reference service with
multi-tenant authorization, versioned workflow definitions, idempotent execution, audit events, structured
logging, PostgreSQL persistence, Redis coordination, and explicit security boundaries around user-configured
network calls.

The project deliberately separates domain and execution logic from FastAPI and SQLAlchemy. The workflow engine
can be tested without a database, web server, or network, while infrastructure adapters remain replaceable at
the application boundary.

## What is implemented

- FastAPI HTTP API with stable error responses and request IDs.
- User registration, login, access tokens, refresh tokens, and organization membership checks.
- Organization-scoped RBAC with owner, admin, editor, and viewer roles.
- Versioned workflow definitions stored in PostgreSQL.
- Deterministic directed-acyclic-graph validation and topological execution ordering.
- Transform, condition, delay, and HTTP workflow steps.
- Retry policies with bounded exponential backoff.
- Per-step timeouts and failure propagation.
- Redis-backed execution idempotency for duplicate request suppression across API instances.
- SSRF protection for outbound HTTP steps, including private/link-local/loopback address blocking.
- HMAC webhook signing helpers with replay-window validation.
- Argon2 password hashing and one-way API-key hashing helpers.
- Fernet-backed secret encryption abstraction.
- Structured JSON logs, request correlation IDs, Prometheus metrics, liveness and readiness checks.
- Alembic migrations and SQLAlchemy 2 async persistence.
- Docker and Docker Compose for API, PostgreSQL, Redis, and migrations.
- Unit and stack-level integration tests.
- GitHub Actions for linting, formatting, typing, tests, dependency audit, and static security analysis.
- Dependabot configuration for Python and GitHub Actions dependencies.

## Architecture at a glance

```text
HTTP request
    |
    v
FastAPI route  ---> auth/RBAC dependency
    |
    v
Application service  ---> repository/audit ports
    |                         |
    |                         v
    |                   SQLAlchemy adapters
    v
Workflow engine  ---> step executor ---> SSRF guard ---> outbound HTTP
    |
    v
Redis idempotency adapter
```

The core rule is simple: **domain and execution modules do not depend on FastAPI**. HTTP details stay at the API
edge, persistence details stay in infrastructure modules, and orchestration behavior stays independently
executable and testable.

See [docs/architecture.md](docs/architecture.md) for component boundaries, data flow, concurrency assumptions,
and failure semantics.

## Repository layout

```text
relayforge/
├── .github/
│   ├── dependabot.yml
│   └── workflows/
│       ├── ci.yml
│       └── security.yml
├── docs/
│   ├── adr/
│   ├── api-examples.md
│   ├── architecture.md
│   ├── deployment.md
│   ├── testing.md
│   └── threat-model.md
├── migrations/
│   └── versions/
├── scripts/
├── src/relayforge/
│   ├── api/
│   ├── application/
│   ├── domain/
│   ├── execution/
│   ├── infra/
│   └── security/
├── tests/
│   ├── integration/
│   └── unit/
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── pyproject.toml
```

## Requirements

For local Python development:

- Python 3.12+
- PostgreSQL 16+
- Redis 7+

For containerized development, Docker with Compose support is sufficient.

## Fresh clone setup

### Option A: Docker Compose

Generate a local JWT signing secret and export it before starting the stack:

```bash
export RELAYFORGE_JWT_SECRET="$(python scripts/generate-secret.py)"
docker compose up --build
```

On PowerShell:

```powershell
$env:RELAYFORGE_JWT_SECRET = python scripts/generate-secret.py
docker compose up --build
```

Compose starts PostgreSQL and Redis, runs `alembic upgrade head`, then starts the API on port `8000`.

Verify it:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Expected readiness shape:

```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "redis": "ok"
  }
}
```

Interactive OpenAPI documentation is available at `/docs` in development.

### Option B: Python environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

Set a real local development signing secret in `.env`, start PostgreSQL and Redis, then apply migrations:

```bash
alembic upgrade head
uvicorn relayforge.main:app --reload
```

Do not commit `.env`. It is ignored by Git.

## Quality checks

The standard local verification sequence is:

```bash
ruff check src tests
ruff format --check src tests
mypy src/relayforge
pytest
```

Or:

```bash
make check
```

A helper script reproduces a clean virtual-environment check:

```bash
./scripts/fresh-clone-check.sh
```

The current unit suite exercises workflow graph validation, step resolution, retries, timeouts, idempotency,
SSRF rules, token semantics, password hashing, encrypted secrets, webhook authentication, execution state,
tenant isolation, application services, and serialization. Stack integration tests exercise PostgreSQL, Redis,
authentication, persistence, routing, and end-to-end workflow execution.

The repository currently enforces a **60% total branch-aware coverage floor** while the HTTP and persistence
adapter tests are expanded. Core domain and security modules are materially higher than the repository-wide
number. The explicit next coverage milestone is 80%; see [docs/testing.md](docs/testing.md).

## Security model

RelayForge assumes workflow definitions are user-controlled data. They are never evaluated as Python source.
Transform expressions use a restricted dotted-path resolver such as `$input.customer.id` and
`$steps.fetch.body.id`.

Outbound HTTP steps are protected by a destination policy that:

1. permits only HTTP and HTTPS,
2. rejects embedded URL credentials,
3. resolves the destination hostname before the request,
4. rejects loopback, private, link-local, multicast, reserved, and unspecified IP addresses,
5. optionally enforces an exact host allowlist,
6. disables automatic redirect following in the HTTP executor,
7. caps accepted upstream response size.

Production startup requires an explicitly configured JWT secret and encryption key. Passwords are hashed with
Argon2, API keys are stored only as SHA-256 digests, and secret values can be encrypted before persistence.

See [docs/threat-model.md](docs/threat-model.md) and [SECURITY.md](SECURITY.md).

## Example: register

```bash
curl -X POST http://localhost:8000/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "developer@example.com",
    "password": "a-long-local-development-password",
    "organization_name": "Example Org"
  }'
```

The response includes access and refresh tokens. Use the access token as a Bearer token for workflow endpoints.

## Example: create a workflow

```bash
curl -X POST http://localhost:8000/v1/workflows \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Customer enrichment",
    "description": "Shapes an incoming customer payload",
    "steps": [
      {
        "id": "shape",
        "name": "Normalize fields",
        "type": "transform",
        "mapping": {
          "customer_id": "$input.customer.id",
          "email": "$input.customer.email",
          "source": "api"
        }
      },
      {
        "id": "eligible",
        "name": "Check account age",
        "type": "condition",
        "depends_on": ["shape"],
        "source": "$input.customer.account_age_days",
        "operator": "gte",
        "value": 30
      }
    ]
  }'
```

Workflow definitions are versioned on update. A workflow update creates a new immutable definition version
instead of overwriting historical configuration in place.

## Example: execute idempotently

```bash
curl -X POST "http://localhost:8000/v1/workflows/$WORKFLOW_ID/execute" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: customer-enrichment-42-v1' \
  -d '{
    "input": {
      "customer": {
        "id": 42,
        "email": "customer@example.com",
        "account_age_days": 90
      }
    }
  }'
```

A repeated request with the same workflow/version/idempotency key returns the stored completed execution rather
than running the workflow a second time.

More examples are in [docs/api-examples.md](docs/api-examples.md).

## Workflow execution semantics

A workflow is valid only when every dependency references an existing step and the dependency graph is acyclic.
The engine computes a deterministic topological ordering before execution.

Each step moves through a small state machine:

```text
pending -> running -> succeeded
                  \-> failed
```

The workflow itself moves through:

```text
pending -> running -> succeeded
                  \-> failed
```

A failed step stops subsequent dependent execution in the current v0.1 sequential engine. Retry attempts occur
inside the step boundary and use a bounded exponential delay. Per-step timeout is enforced with `asyncio.wait_for`.

## Multi-tenancy

Tokens carry the selected organization identifier, but authorization does not trust that claim by itself. Each
protected request checks that the user is still active and still has a membership row for the token's organization.
Workflow repository lookups also include `organization_id`, reducing accidental cross-tenant reads at the query
boundary.

The current roles are:

| Role | Read workflows | Create/update workflows | Administrative scope |
| --- | --- | --- | --- |
| owner | yes | yes | intended full organization control |
| admin | yes | yes | intended delegated administration |
| editor | yes | yes | workflow authoring |
| viewer | yes | no | read/execute only |

Organization administration endpoints are intentionally outside the v0.1 scope.

## Database evolution

Alembic owns schema evolution:

```bash
alembic upgrade head
alembic downgrade -1
```

Never edit an already-deployed migration to change production history. Add a new revision instead.

## Observability

HTTP requests are logged as JSON and include a request ID, method, path, status, and duration. Clients may supply
`X-Request-ID`; RelayForge returns it in the response. Unhandled workflow step failures are logged with execution
and workflow identifiers without logging user credentials or secret values.

Prometheus metrics are exposed at `/metrics`. Liveness reports process availability. Readiness verifies PostgreSQL
and Redis before reporting healthy.

## Dependency maintenance

`pyproject.toml` uses bounded dependency ranges and CI installs from a clean environment. Dependabot checks both
Python dependencies and GitHub Actions weekly. The security workflow runs `pip-audit` and Bandit and rejects
several common committed credential formats.

A future release may add a fully pinned deployment lock produced by `uv lock` or another agreed lock strategy.
For library-style editable development, `pyproject.toml` remains the canonical dependency declaration today.

## Development principles

- Prefer explicit domain types over unstructured dictionaries at boundaries.
- Keep route handlers thin.
- Keep network and persistence concerns behind adapters.
- Add a regression test with every bug fix.
- Never weaken a test solely to make an implementation pass.
- Never commit credentials, tokens, private keys, or `.env` files.
- Avoid arbitrary evaluation of workflow/user data.
- Keep files cohesive rather than creating large “god modules.”
- Make each commit about one behavioral change whenever practical.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Known limitations

RelayForge is deliberately honest about its current boundaries:

- The v0.1 engine executes steps sequentially even when branches could safely run in parallel.
- Workflow cancellation is represented in the domain enum but no cancellation endpoint is implemented yet.
- Organization administration and invitation flows are not implemented yet.
- Refresh-token rotation/revocation storage is not implemented yet.
- HTTP allowlisting supports exact hosts, not wildcard policies.
- Execution persistence is modeled in the database schema but the synchronous API currently returns the engine
  result directly; durable per-step execution journaling is planned.
- Distributed idempotency stores completed runs in Redis with a finite TTL. Long-term execution history belongs in
  PostgreSQL in the planned durable execution milestone.

These are tracked as architectural follow-ups rather than hidden behind placeholder code.

## Roadmap

### 0.2: durable execution

- Persist execution and step-attempt records transactionally.
- Introduce worker-owned execution via Redis queue.
- Support cancellation and lease/heartbeat semantics.
- Raise repository coverage floor toward 80% with adapter-level tests.

### 0.3: scheduling and webhooks

- Signed inbound webhooks.
- Cron/schedule trigger model.
- Replay protection persistence.
- Secret references inside workflow definitions.

### 0.4: parallel branches

- Execute dependency-independent steps concurrently.
- Add bounded organization-level concurrency.
- Introduce deterministic join semantics and failure policies.

## Documentation

- [Architecture](docs/architecture.md)
- [Threat model](docs/threat-model.md)
- [Testing strategy](docs/testing.md)
- [Deployment](docs/deployment.md)
- [API examples](docs/api-examples.md)
- [Architecture decisions](docs/adr/)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## License

MIT. See [LICENSE](LICENSE).
