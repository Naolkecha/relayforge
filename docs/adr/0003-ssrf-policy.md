# ADR 0003: Treat outbound workflow HTTP as an SSRF boundary

- Status: Accepted
- Date: 2026-08-14

## Context

Workflow authors control outbound URLs. Without controls, an HTTP step can access loopback services, private
networks, cloud metadata endpoints, or management APIs reachable by the RelayForge workload.

## Decision

Every HTTP step validates its destination before connection. Only HTTP(S) is supported; URL credentials are
rejected; DNS is resolved; special/private addresses are blocked; optional exact-host allowlisting is supported;
redirect following is disabled; response size is bounded.

## Consequences

This blocks common SSRF paths at the application layer but does not eliminate DNS rebinding races. Production
deployments must still use egress firewall/network policy. If stronger guarantees are required, the connector
must pin the validated peer address while retaining TLS hostname verification.
