from __future__ import annotations

from typing import Protocol
from uuid import UUID

from relayforge.domain.audit import AuditEvent
from relayforge.domain.workflow import WorkflowDefinition


class WorkflowRecord(Protocol):
    id: UUID
    organization_id: UUID
    name: str
    version: int
    definition: WorkflowDefinition


class WorkflowRepository(Protocol):
    async def get(self, workflow_id: UUID, organization_id: UUID) -> WorkflowRecord | None: ...

    async def create(
        self,
        *,
        organization_id: UUID,
        name: str,
        definition: WorkflowDefinition,
        created_by: UUID,
    ) -> WorkflowRecord: ...

    async def update_definition(
        self,
        *,
        workflow_id: UUID,
        organization_id: UUID,
        definition: WorkflowDefinition,
        updated_by: UUID,
    ) -> WorkflowRecord: ...


class AuditRepository(Protocol):
    async def append(self, event: AuditEvent) -> None: ...
