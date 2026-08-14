# ADR 0001: Keep workflow core independent of web and persistence frameworks

- Status: Accepted
- Date: 2026-08-14

## Context

Workflow orchestration contains graph validation, state transitions, retry semantics, timeout behavior, and
expression resolution. If this logic lives in FastAPI route functions or SQLAlchemy models, it becomes difficult
to test deterministically and difficult to reuse in future worker processes.

## Decision

The domain and execution layers will not import FastAPI or SQLAlchemy. Application services depend on repository
protocols. API and infrastructure modules adapt external systems to those boundaries.

## Consequences

Positive:

- core behavior runs in fast unit tests,
- worker processes can reuse execution code,
- storage technology can change without rewriting graph logic,
- HTTP concerns do not leak into domain state.

Costs:

- additional adapter/protocol types,
- explicit translation at boundaries,
- developers must resist bypassing application services for convenience.
