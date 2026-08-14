# RelayForge architecture

## Goals

RelayForge is built around five architectural goals:

1. Workflow behavior must be testable without HTTP, a database, or Redis.
2. Multi-tenant access checks must occur at more than one boundary.
3. User-defined workflow data must never become executable Python code.
4. Network actions must have an explicit security policy because workflow authors control destinations.
5. Operational behavior must be visible through structured logs, metrics, and health checks.

## Layer boundaries

### Domain

`relayforge.domain` contains business values and execution state. It has no dependency on FastAPI, SQLAlchemy,
Redis, or HTTP clients.

Important types include:

- `WorkflowDefinition`, the validated immutable workflow document.
- step definitions (`HttpStep`, `TransformStep`, `ConditionStep`, `DelayStep`).
- `RetryPolicy`, including deterministic backoff calculation.
- `WorkflowRun` and `StepRun`, the execution state model.
- `AuditEvent`, an immutable description of a security/business-relevant action.

The domain is intentionally small. Infrastructure-specific behavior does not belong there.

### Execution

`relayforge.execution` owns orchestration mechanics.

`ExecutionContext` resolves a restricted expression grammar. Supported references currently include:

- `$input`
- `$input.<path>`
- `$steps.<step-id>`
- `$steps.<step-id>.<path>`

No expressions are passed to `eval`, `exec`, a template interpreter, shell, or SQL engine.

`WorkflowEngine` validates the graph, checks idempotency, creates execution state, runs steps in deterministic
order, applies retry policy, enforces timeouts, records step state, and produces a final `WorkflowRun`.

`DefaultStepExecutor` owns concrete step behavior. This split allows the engine to be tested with deterministic
fake executors and allows future executor implementations to be sandboxed or moved out-of-process.

### Application

`relayforge.application` coordinates use cases. It depends on repository protocols rather than concrete SQLAlchemy
classes. Application services also emit audit events after state-changing operations.

The service layer is where transaction ownership and authorization policy can grow without putting business logic
inside route functions.

### API

`relayforge.api` is the HTTP adapter. It handles:

- request/response validation,
- JWT extraction,
- membership revalidation,
- RBAC dependencies,
- idempotency headers,
- request correlation IDs,
- status codes and stable error envelopes.

API handlers translate inputs to application calls. They should not contain graph algorithms, password hashing,
or raw SQL.

### Infrastructure

`relayforge.infra` contains implementations that talk to external systems:

- SQLAlchemy models/session management,
- PostgreSQL repositories,
- Redis job queue adapter,
- Redis execution idempotency adapter.

Infrastructure can import domain/application types. The reverse dependency is avoided through protocols.

### Security

`relayforge.security` collects security-specific primitives and policy:

- Argon2 password hashing,
- JWT creation/verification,
- API-key generation and digesting,
- webhook HMAC signing/verification,
- Fernet authenticated secret encryption,
- SSRF destination validation.

Keeping these concerns explicit makes security review easier than scattering ad hoc helper functions across
routes and models.

## Request flow

A protected workflow request follows this path:

1. FastAPI extracts the Bearer token.
2. `TokenService` verifies signature, issuer, expiry, required claims, and token kind.
3. The dependency converts subject/organization claims to UUIDs.
4. PostgreSQL is queried to confirm the user is active and still belongs to that organization.
5. Role dependencies reject unauthorized mutations.
6. The repository includes `organization_id` in workflow lookups.
7. The application service executes the use case.
8. Audit metadata is persisted in the same request-scoped SQLAlchemy transaction.
9. Middleware returns the request ID and records latency metrics.

This is defense in depth. A valid JWT alone is not sufficient if the membership has been removed.

## Workflow graph validation

Each step may depend on zero or more step IDs. Validation builds:

- a set of known IDs,
- an indegree count per step,
- an adjacency list from dependency to dependent step.

Unknown dependencies fail before execution. Kahn's algorithm computes a deterministic topological order. The
ready queue is sorted to avoid definition-order accidents for independent steps. If the number of emitted nodes
is smaller than the number of steps, the remaining positive-indegree nodes participate in at least one cycle and
the workflow is rejected.

Complexity is O(V + E), excluding deterministic sorting of ready/outgoing identifiers.

## Retry semantics

A step's `RetryPolicy` includes:

- `max_attempts`,
- `initial_delay_seconds`,
- `multiplier`,
- `max_delay_seconds`.

Attempt one has no delay. Later attempts use bounded exponential backoff. A step timeout applies independently to
each attempt. Exhaustion moves the step to failed and the workflow to failed.

A future asynchronous worker implementation should add retry classification so permanent 4xx-style failures are
not retried blindly.

## Idempotency

The engine derives an internal digest from:

```text
workflow_id + workflow_version + caller-provided idempotency key
```

Completed execution state is stored in Redis using atomic `SET ... NX` semantics. If two API instances race, one
completed result wins the insertion and the loser re-reads the winner. The current design stores completed
results, not an in-progress lease. Therefore simultaneous duplicate requests may both perform side effects before
completion.

This is an explicitly documented limitation. The durable execution milestone will acquire an in-progress lease
before side-effecting execution and persist execution state in PostgreSQL.

## Outbound HTTP security

HTTP workflow steps are unusually sensitive because untrusted users choose a destination. Before each request:

1. parse the URL,
2. require `http` or `https`,
3. reject username/password URL components,
4. normalize the hostname,
5. enforce the optional exact-host allowlist,
6. resolve DNS,
7. reject any private/special IP result.

The executor disables automatic redirects because redirect chains can otherwise bypass a one-time destination
check. Response bodies are size-limited before being accepted into workflow state.

A production hardening step would revalidate the connected peer address to reduce DNS rebinding risk between
resolution and connection. See the threat model.

## Data model

### users

Stores normalized email, Argon2 password hash, active status, and timestamps.

### organizations

Defines the tenant boundary. Slugs are globally unique.

### memberships

Connects users to organizations with one role per membership. The `(organization_id, user_id)` pair is unique.

### workflows

Stores tenant ownership, current status/version, and creator identity. Workflow names are unique per organization.

### workflow_versions

Stores immutable serialized definitions. `(workflow_id, version)` is unique.

### executions

Prepared for durable execution history: workflow/version, input, output, status, timestamps, error, and an
idempotency digest.

### audit_events

Append-oriented action metadata with organization, actor, resource, and timestamp.

### api_keys

Stores only a SHA-256 key digest plus a short non-secret prefix for display and revocation metadata.

## Transactions

`Database.session()` owns commit/rollback for one request-scoped unit of work. Repository methods flush when they
need generated identifiers but do not commit independently. This lets application services persist business state
and audit events atomically in the same session.

Long-running workflow execution should eventually move outside request transactions. Durable workers should use
short transactions around state transitions rather than holding a database transaction open while making network
calls.

## Observability

Structured logs are emitted as compact JSON. Request middleware adds:

- `request_id`,
- HTTP method,
- path,
- status,
- duration.

The workflow engine logs failed attempts with execution and step identity while avoiding user secrets.
Prometheus counters and histograms capture HTTP request count and latency. Readiness separately evaluates
PostgreSQL and Redis.

## Scaling assumptions

The API is stateless except for external PostgreSQL and Redis dependencies. Multiple API processes can therefore
serve traffic behind a reverse proxy. Distributed completed-result idempotency already uses Redis.

The current synchronous execution path is suitable for short workflows. Long-running work should move to worker
processes so API request lifetime is not coupled to workflow duration.

## Design constraints for future work

Any parallel execution implementation must preserve:

- deterministic dependency satisfaction,
- bounded concurrency,
- cancellation propagation,
- idempotent side-effect semantics,
- observable per-step state,
- stable final run serialization.

Any plugin/custom-code step must run outside the API process in a constrained sandbox. RelayForge should not add a
Python-eval step to the existing engine.
