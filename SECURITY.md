# Security policy

## Supported versions

RelayForge is currently pre-1.0. Security fixes are applied to the latest main branch and the most recent release
once tagged releases exist.

## Reporting a vulnerability

Do not publish exploit details in a public issue when the vulnerability could expose credentials, cross tenant
boundaries, enable SSRF, execute arbitrary code, bypass authentication, or corrupt durable workflow state.

For a real deployed fork, configure a private security contact or repository security advisory workflow before
accepting external users. This source repository does not publish a personal email address for vulnerability
reports.

A useful private report includes:

- affected version/commit,
- vulnerability class,
- reproduction steps,
- expected vs actual behavior,
- security impact,
- suggested mitigation if known.

## Security-sensitive areas

Reviewers should treat changes to these modules as security-relevant:

- `src/relayforge/security/`
- `src/relayforge/api/dependencies.py`
- authentication application services,
- organization-scoped repositories,
- workflow HTTP execution,
- serialization of execution state,
- migrations involving users, memberships, API keys, or secrets.

## Secret handling

Never commit real credentials. If a secret enters Git history, assume it is compromised and rotate it. Removing it
from the latest file does not invalidate copies in previous commits, forks, caches, or provider logs.

Production secrets belong in a secret manager or runtime environment injection mechanism, not image layers or
repository files.

## Dependency security

The security workflow runs dependency auditing and static analysis. Dependabot proposes updates weekly. A green
scanner result is supporting evidence, not proof that the application is vulnerability-free.

## Network security

RelayForge contains application-level SSRF controls. Production deployments should additionally restrict egress at
the network layer. See `docs/threat-model.md` for residual DNS rebinding and internal-network risks.
