# ADR 0002: Use restricted data-path expressions instead of arbitrary evaluation

- Status: Accepted
- Date: 2026-08-14

## Context

Workflow products often need to reference input and previous step output. The easiest implementation is an
expression engine or Python `eval`, but arbitrary evaluation dramatically expands remote-code-execution risk and
makes authorization/sandboxing far harder.

## Decision

RelayForge v0.x supports a deliberately narrow dotted-path grammar rooted at `$input` or `$steps.<id>`. Literal
mapping values remain literal. No Python, shell, or template expression evaluation is supported.

## Consequences

Positive:

- small auditable attack surface,
- deterministic behavior,
- straightforward tests,
- no in-process code execution from workflow data.

Costs:

- less expressive transformations,
- richer transformations require adding explicit safe operations,
- users cannot run arbitrary custom scripts inside the API process.

Any future custom-code feature requires a separate sandbox architecture and new ADR.
