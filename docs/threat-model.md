# Threat model

## Scope

This document covers the RelayForge API, PostgreSQL persistence, Redis coordination, authentication primitives,
and outbound workflow HTTP actions. Infrastructure controls such as cloud IAM, host hardening, TLS termination,
and managed database configuration are deployment responsibilities but are mentioned where they affect the
application boundary.

## Assets

Primary assets include:

- user credentials,
- JWT signing material,
- encrypted connector secrets,
- organization membership and role data,
- workflow definitions,
- workflow inputs/outputs,
- audit events,
- API keys,
- access to network destinations reachable from the service environment.

## Trust boundaries

### Internet to API

All request bodies, headers, JWTs, idempotency keys, and workflow definitions are untrusted.

### API to PostgreSQL

The application trusts PostgreSQL for durable tenant/auth state but still scopes queries explicitly by tenant.

### API to Redis

Redis is trusted as a coordination store, not as an authorization source. Compromise of Redis can corrupt cached
execution results, so secrets are not stored there in plaintext by design.

### Workflow engine to external network

This is the highest-risk functional boundary because a workflow author can specify a URL. SSRF policy must run
before every outbound request.

## Threats and mitigations

### Credential theft from source control

**Threat:** developers commit tokens, cloud credentials, private keys, or `.env` files.

**Mitigations:**

- `.env` and derived environment files are ignored.
- `.env.example` contains names/placeholders only.
- CI rejects common high-risk credential patterns.
- production startup requires explicit runtime secret configuration.
- dependency/security workflow runs on pushes, pull requests, and weekly schedule.

**Residual risk:** pattern checks are not a complete secret scanner. Repository hosting should also enable secret
scanning where available.

### Password database compromise

**Threat:** an attacker obtains the users table and attempts offline password cracking.

**Mitigations:** Argon2 password hashing with deliberate time/memory cost; no plaintext passwords are persisted or
logged.

**Residual risk:** weak user-selected passwords remain guessable. Future authentication policy may add breached
password detection and MFA.

### JWT forgery or misuse

**Threat:** forged, expired, wrong-kind, or cross-organization tokens are used.

**Mitigations:**

- HS256 signature verification with an explicit algorithm list,
- issuer verification,
- required `exp`, `iat`, `sub`, `org`, `kind`, and `jti` claims,
- token-kind checking,
- short access-token TTL,
- active membership revalidation for protected requests.

**Residual risk:** refresh token rotation/revocation is not persisted in v0.1. A stolen refresh token remains valid
until expiration unless broader signing-key rotation occurs.

### Cross-tenant data access

**Threat:** a valid user manipulates resource identifiers to access another organization's workflows.

**Mitigations:**

- current organization is carried in a verified token,
- membership is revalidated against PostgreSQL,
- repository workflow lookup includes both `workflow_id` and `organization_id`,
- role dependencies gate mutations.

**Residual risk:** every future repository method must preserve tenant scoping. Code review and integration tests
should treat missing organization predicates as high severity.

### SSRF to cloud metadata or internal services

**Threat:** user-configured HTTP steps target `localhost`, RFC1918 networks, link-local metadata endpoints, or DNS
names resolving internally.

**Mitigations:**

- scheme allowlist,
- no URL credentials,
- DNS resolution before request,
- private, loopback, link-local, multicast, reserved, and unspecified address rejection,
- optional exact-host allowlist,
- redirects disabled,
- upstream response size cap.

**Residual risk:** a DNS rebinding race can occur between validation resolution and the HTTP client's connection.
High-security deployments should enforce egress firewall policy and/or connect to the validated address while
preserving TLS hostname verification. Network policy is the final control against SSRF.

### Arbitrary code execution through workflow expressions

**Threat:** a workflow author injects Python, shell, or template expressions.

**Mitigations:** transform/condition sources use a small dotted-path resolver. There is no `eval`, `exec`, shell
invocation, or dynamic import path in workflow execution.

**Residual risk:** a future custom-code feature would fundamentally change the threat model and must be isolated in
an external sandbox rather than added to the API process.

### Webhook spoofing and replay

**Threat:** an attacker forges or replays webhook payloads.

**Mitigations:** HMAC-SHA256 signature helper binds timestamp and body; constant-time comparison; timestamp
replay-window enforcement.

**Residual risk:** v0.1 exposes helpers but does not persist used webhook event IDs. A replay inside the allowed
window cannot yet be detected by event identity.

### Duplicate side effects

**Threat:** clients retry a request and execute an external side effect multiple times.

**Mitigations:** workflow/version/idempotency key maps to a Redis completed execution; subsequent completed retries
return the existing run.

**Residual risk:** current idempotency acquisition occurs after execution completion. Two simultaneous first-time
requests can race and both perform work. Durable execution will introduce an in-progress lease/state row before
side effects.

### Sensitive data in logs

**Threat:** credentials or connector secrets are written to application logs.

**Mitigations:** logging calls use identifiers/status metadata and do not intentionally log passwords, JWTs, API
keys, workflow secret values, or request bodies.

**Residual risk:** exceptions from third-party libraries may contain URLs or upstream details. Production log
pipelines should apply additional redaction and access controls.

### Dependency compromise

**Threat:** vulnerable or malicious third-party packages/actions enter the build.

**Mitigations:** bounded dependency ranges, Dependabot, `pip-audit`, Bandit, pinned major GitHub Action references,
and code review.

**Residual risk:** dependencies are not fully locked in v0.1. A deployment lockfile should be added before strict
supply-chain reproducibility is claimed.

## Security invariants

The following are review blockers:

1. Production credentials must not be committed.
2. Workflow expressions must not use arbitrary code evaluation.
3. Workflow resource access must be organization-scoped.
4. Outbound HTTP destinations must pass SSRF validation.
5. Passwords must never be persisted or logged in plaintext.
6. API keys must not be persisted in raw form.
7. Security failures must fail closed rather than silently continuing.

## Incident response expectations

If a credential is accidentally committed:

1. rotate/revoke it immediately,
2. remove it from current source,
3. assess whether Git history cleanup is necessary,
4. inspect audit/provider logs for use,
5. add a regression control that would have blocked the same pattern,
6. document the incident privately according to organization policy.

Deleting a secret from the latest commit is not sufficient because repository history may still expose it.
