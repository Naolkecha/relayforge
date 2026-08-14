# Suggested real development commit sequence

This is a workflow for future work, not fabricated repository history. Make a commit only after the corresponding
work is actually implemented and verified.

1. `chore: establish python project and quality tooling`
2. `feat: model workflow definitions and validate dependency graphs`
3. `test: cover workflow graph and retry invariants`
4. `feat: implement deterministic workflow execution engine`
5. `feat: add restricted transform and condition execution`
6. `security: enforce outbound http ssrf policy`
7. `test: cover ssrf, timeout, retry, and idempotency behavior`
8. `feat: add postgres models and alembic schema`
9. `feat: add registration tokens and organization membership checks`
10. `feat: persist versioned workflows with audit events`
11. `feat: add redis-backed execution idempotency`
12. `test: add postgres redis stack integration test`
13. `ci: enforce lint typing tests and security scans`
14. `docs: document architecture threat model and deployment`

Do not create these commits retroactively just to increase commit count. If the repository begins from a scaffold,
commit that scaffold once, then make future changes in focused commits with their tests.
