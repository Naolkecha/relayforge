# Changelog

All notable changes to RelayForge are documented here. The format follows Keep a Changelog concepts and the
project intends to use semantic versioning once releases begin.

## Unreleased

### Added

- Stack integration test covering authentication, persistence, workflow execution, and Redis idempotency.
- Security workflow with dependency audit, Bandit scan, and credential-pattern check.
- Dependabot configuration for Python and GitHub Actions.

### Changed

- Documented the current 60% repository coverage floor and 80% milestone instead of overstating adapter coverage.

## 0.1.0 - 2026-08-14

### Added

- FastAPI application factory and operational endpoints.
- Structured request logging with correlation IDs and Prometheus metrics.
- PostgreSQL async database layer and initial Alembic migration.
- User, organization, membership, workflow, version, execution, audit, and API-key schema.
- Registration/login/refresh application service using Argon2 password hashing and JWTs.
- Organization membership revalidation and role-based route dependencies.
- Immutable workflow definitions with HTTP, transform, condition, and delay steps.
- Deterministic DAG validation and cycle detection.
- Framework-independent workflow execution engine.
- Retry policies, bounded exponential backoff, per-step timeouts, and failure state tracking.
- Restricted dotted-path execution context instead of arbitrary expression evaluation.
- SSRF guard for user-configured HTTP destinations.
- Outbound HTTP response status and size enforcement.
- Redis completed-execution idempotency adapter.
- HMAC webhook signing/verification helpers.
- API-key generation and one-way digest helpers.
- Fernet authenticated secret encryption helper.
- Dockerfile and Compose stack for API, PostgreSQL, Redis, and migrations.
- Unit tests across graph validation, execution, security, serialization, and application services.
- CI quality gates and developer documentation.
