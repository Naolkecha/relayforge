# ADR 0004: Scope execution idempotency to workflow version

- Status: Accepted with known limitation
- Date: 2026-08-14

## Context

Clients retry API calls after timeouts and network failures. Running a workflow twice can duplicate outbound side
effects. An idempotency key should prevent accidental replay while allowing a new workflow version to execute
independently.

## Decision

The idempotency digest includes workflow ID, workflow version, and the caller's key. Completed results are stored
in Redis with atomic `SET NX` and a finite TTL.

## Known limitation

The v0.1 engine writes the idempotency record after execution completes. Concurrent duplicate first requests may
both perform side effects before one completed result wins the Redis insertion.

The durable execution milestone will acquire an in-progress execution lease before running side effects and store
canonical execution history in PostgreSQL.
