from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from relayforge.application.ports import AuditRepository, WorkflowRecord, WorkflowRepository
from relayforge.domain.audit import AuditEvent
from relayforge.domain.execution import WorkflowRun
from relayforge.domain.workflow import WorkflowDefinition
from relayforge.errors import NotFoundError
from relayforge.execution.engine import WorkflowEngine


@dataclass(slots=True)
class WorkflowService:
    workflows: WorkflowRepository
    audit: AuditRepository

    async def create(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        definition: WorkflowDefinition,
    ) -> WorkflowRecord:
        definition.validated_order()
        record = await self.workflows.create(
            organization_id=organization_id,
            name=definition.name,
            definition=definition,
            created_by=actor_id,
        )
        await self.audit.append(
            AuditEvent(
                organization_id=organization_id,
                actor_id=actor_id,
                action="workflow.created",
                resource_type="workflow",
                resource_id=str(record.id),
                metadata={"version": record.version, "step_count": len(definition.steps)},
            )
        )
        return record

    async def update(
        self,
        *,
        workflow_id: UUID,
        organization_id: UUID,
        actor_id: UUID,
        definition: WorkflowDefinition,
    ) -> WorkflowRecord:
        definition.validated_order()
        record = await self.workflows.update_definition(
            workflow_id=workflow_id,
            organization_id=organization_id,
            definition=definition,
            updated_by=actor_id,
        )
        await self.audit.append(
            AuditEvent(
                organization_id=organization_id,
                actor_id=actor_id,
                action="workflow.updated",
                resource_type="workflow",
                resource_id=str(workflow_id),
                metadata={"version": record.version},
            )
        )
        return record


@dataclass(slots=True)
class ExecutionService:
    workflows: WorkflowRepository
    engine: WorkflowEngine
    audit: AuditRepository

    async def execute(
        self,
        *,
        workflow_id: UUID,
        organization_id: UUID,
        actor_id: UUID | None,
        input_data: dict[str, Any],
        idempotency_key: str | None,
    ) -> WorkflowRun:
        record = await self.workflows.get(workflow_id, organization_id)
        if record is None:
            raise NotFoundError("workflow not found")
        run = await self.engine.run(
            workflow_id=record.id,
            definition=record.definition,
            input_data=input_data,
            idempotency_key=idempotency_key,
        )
        await self.audit.append(
            AuditEvent(
                organization_id=organization_id,
                actor_id=actor_id,
                action="workflow.executed",
                resource_type="workflow_execution",
                resource_id=str(run.id),
                metadata={
                    "workflow_id": str(workflow_id),
                    "workflow_version": record.version,
                    "status": run.status.value,
                },
            )
        )
        return run
