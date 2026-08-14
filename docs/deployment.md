# Deployment guide

## Deployment model

RelayForge is a stateless API process backed by PostgreSQL and Redis. A typical production topology is:

```text
Internet
   |
TLS load balancer / reverse proxy
   |
RelayForge API replicas
   |             |
PostgreSQL      Redis
```

The current release executes workflows in API processes, so request timeout settings must exceed the maximum
expected short workflow duration. The roadmap moves execution to dedicated workers.

## Required configuration

Production should explicitly configure:

- `RELAYFORGE_ENVIRONMENT=production`
- `RELAYFORGE_DATABASE_URL`
- `RELAYFORGE_REDIS_URL`
- `RELAYFORGE_JWT_SECRET`
- `RELAYFORGE_ENCRYPTION_KEY`
- `RELAYFORGE_LOG_LEVEL`
- optional `RELAYFORGE_ALLOWED_HTTP_HOSTS`
- optional `RELAYFORGE_BLOCK_PRIVATE_NETWORKS`

The application refuses production startup without an explicit JWT secret and encryption key.

## Secret management

Do not bake secrets into the image, Compose file, Helm values committed to source, or CI logs. Use the deployment
platform's secret manager and inject values at runtime.

The JWT signing secret should be high entropy. Rotation requires a planned token invalidation strategy because the
current TokenService accepts one signing key at a time.

Fernet encryption keys protect encrypted connector data at rest in the application layer. Back up and rotate them
carefully because losing the key makes encrypted values unrecoverable.

## Database migration

Run schema migration as a release step before starting new application instances:

```bash
alembic upgrade head
```

Back up production data before destructive migrations. Prefer expand/contract schema changes for zero-downtime
releases:

1. deploy additive schema,
2. deploy code that can use old/new forms,
3. backfill,
4. switch reads/writes,
5. remove old schema in a later release.

## Container image

The Dockerfile uses a builder stage and a slim Python runtime. The final process runs as a non-root `relayforge`
user and exposes a liveness `HEALTHCHECK`.

Build:

```bash
docker build -t relayforge:0.1.0 .
```

Run only after supplying external database/Redis URLs and secrets.

## TLS and proxy behavior

Terminate TLS at a trusted reverse proxy or service mesh. The Uvicorn command accepts proxy headers, so only place
it behind infrastructure that sanitizes/sets forwarded headers correctly. Do not expose a proxy-header-trusting
service directly to arbitrary networks if client IP attribution matters.

## PostgreSQL

Recommended production controls:

- managed service or replicated PostgreSQL,
- TLS connections,
- least-privilege application role,
- automated backups with tested restore,
- connection limits aligned with API replica count,
- statement/lock monitoring,
- migration role separated from runtime role where practical.

## Redis

Redis stores coordination/idempotency data, not the authorization source of truth. Recommended controls:

- private network placement,
- TLS/authentication where supported,
- eviction policy chosen with idempotency TTL needs in mind,
- monitoring for memory pressure,
- persistence according to acceptable duplicate-execution risk.

If Redis loses idempotency entries, the consequence is potential re-execution of requests, not loss of canonical
workflow definitions.

## Egress policy

Application-level SSRF protection is not a substitute for network controls. Production should deny arbitrary
egress and allow only destinations required by product policy. Cloud metadata endpoints and internal management
networks should be unreachable from the API workload.

## Health checks

- `/health/live`: process is serving requests.
- `/health/ready`: PostgreSQL and Redis are available.

A load balancer should remove an instance from traffic when readiness fails while allowing enough restart grace to
avoid loops during dependency outages.

## Observability

Collect stdout/stderr as structured JSON. Preserve `request_id` for correlation. Scrub logs again at the platform
layer if organizational policy requires it.

Scrape `/metrics` from a trusted monitoring network. The endpoint should not be exposed publicly in high-security
deployments.

## Rollback

Application rollback is safe only while the old binary remains compatible with the migrated schema. This is why
expand/contract migration style is preferred. Never assume `alembic downgrade` is a safe production rollback for
migrations that destroy or transform data.
