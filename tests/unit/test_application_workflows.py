from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest

from relayforge.application.workflows import ExecutionService, WorkflowService
from relayforge.domain.audit import AuditEvent
from relayforge.domain.common import ExecutionStatus
from relayforge.domain.workflow import TransformStep, WorkflowDefinition
from relayforge.errors import NotFoundError
from relayforge.execution.engine import WorkflowEngine
from relayforge.execution.idempotency import MemoryIdempotencyStore


@dataclass(slots=True)
class FakeRecord:
    id: UUID
    organization_id: UUID
    name: str
    version: int
    definition: WorkflowDefinition


class FakeWorkflowRepository:
    def __init__(self) -> None:
        self.records: dict[UUID, FakeRecord] = {}

    async def get(self, workflow_id: UUID, organization_id: UUID) -> FakeRecord | None:
        record = self.records.get(workflow_id)
        return record if record and record.organization_id == organization_id else None

    async def create(
        self,
        *,
        organization_id: UUID,
        name: str,
        definition: WorkflowDefinition,
        created_by: UUID,
    ) -> FakeRecord:
        del created_by
        record = FakeRecord(uuid4(), organization_id, name, 1, definition)
        self.records[record.id] = record
        return record

    async def update_definition(
        self,
        *,
        workflow_id: UUID,
        organization_id: UUID,
        definition: WorkflowDefinition,
        updated_by: UUID,
    ) -> FakeRecord:
        del updated_by
        current = await self.get(workflow_id, organization_id)
        if current is None:
            raise NotFoundError("workflow not found")
        record = FakeRecord(
            current.id,
            current.organization_id,
            definition.name,
            current.version + 1,
            definition.model_copy(update={"version": current.version + 1}),
        )
        self.records[workflow_id] = record
        return record


class FakeAuditRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)


class EchoExecutor:
    async def execute(self, step: object, context: object) -> Any:
        del context
        return {"step": step.id}  # type: ignore[attr-defined]


def definition(name: str = "Sample") -> WorkflowDefinition:
    return WorkflowDefinition(
        name=name,
        steps=(TransformStep(id="shape", name="Shape", mapping={"ok": True}),),
    )


@pytest.mark.asyncio
async def test_create_validates_persists_and_audits() -> None:
    workflows = FakeWorkflowRepository()
    audit = FakeAuditRepository()
    service = WorkflowService(workflows=workflows, audit=audit)
    org_id = uuid4()
    actor_id = uuid4()
    record = await service.create(
        organization_id=org_id,
        actor_id=actor_id,
        definition=definition(),
    )
    assert record.organization_id == org_id
    assert audit.events[0].action == "workflow.created"
    assert audit.events[0].actor_id == actor_id
    assert audit.events[0].metadata["step_count"] == 1


@pytest.mark.asyncio
async def test_update_creates_next_version_and_audits() -> None:
    workflows = FakeWorkflowRepository()
    audit = FakeAuditRepository()
    service = WorkflowService(workflows=workflows, audit=audit)
    org_id = uuid4()
    actor_id = uuid4()
    created = await service.create(
        organization_id=org_id,
        actor_id=actor_id,
        definition=definition("v1"),
    )
    updated = await service.update(
        workflow_id=created.id,
        organization_id=org_id,
        actor_id=actor_id,
        definition=definition("v2"),
    )
    assert updated.version == 2
    assert updated.name == "v2"
    assert audit.events[-1].action == "workflow.updated"


@pytest.mark.asyncio
async def test_execution_service_rejects_cross_tenant_lookup() -> None:
    workflows = FakeWorkflowRepository()
    audit = FakeAuditRepository()
    engine = WorkflowEngine(executor=EchoExecutor(), idempotency_store=MemoryIdempotencyStore())
    service = ExecutionService(workflows=workflows, engine=engine, audit=audit)
    owner_org = uuid4()
    created = await WorkflowService(workflows, audit).create(
        organization_id=owner_org,
        actor_id=uuid4(),
        definition=definition(),
    )
    with pytest.raises(NotFoundError):
        await service.execute(
            workflow_id=created.id,
            organization_id=uuid4(),
            actor_id=uuid4(),
            input_data={},
            idempotency_key=None,
        )


@pytest.mark.asyncio
async def test_execution_service_runs_and_audits_status() -> None:
    workflows = FakeWorkflowRepository()
    audit = FakeAuditRepository()
    engine = WorkflowEngine(executor=EchoExecutor(), idempotency_store=MemoryIdempotencyStore())
    service = ExecutionService(workflows=workflows, engine=engine, audit=audit)
    org_id = uuid4()
    created = await WorkflowService(workflows, audit).create(
        organization_id=org_id,
        actor_id=uuid4(),
        definition=definition(),
    )
    run = await service.execute(
        workflow_id=created.id,
        organization_id=org_id,
        actor_id=uuid4(),
        input_data={"hello": "world"},
        idempotency_key="abc",
    )
    assert run.status is ExecutionStatus.SUCCEEDED
    assert audit.events[-1].action == "workflow.executed"
    assert audit.events[-1].metadata["status"] == "succeeded"
