from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relayforge.domain.audit import AuditEvent
from relayforge.domain.workflow import WorkflowDefinition
from relayforge.errors import NotFoundError
from relayforge.infra.db.models import AuditEventModel, WorkflowModel, WorkflowVersionModel


@dataclass(slots=True)
class PersistedWorkflow:
    id: UUID
    organization_id: UUID
    name: str
    version: int
    definition: WorkflowDefinition


class SqlAlchemyWorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, workflow_id: UUID, organization_id: UUID) -> PersistedWorkflow | None:
        query = (
            select(WorkflowModel)
            .where(
                WorkflowModel.id == workflow_id,
                WorkflowModel.organization_id == organization_id,
            )
        )
        model = await self._session.scalar(query)
        if model is None:
            return None
        current = next((v for v in model.versions if v.version == model.current_version), None)
        if current is None:
            raise RuntimeError("workflow current_version references no persisted version")
        return PersistedWorkflow(
            id=model.id,
            organization_id=model.organization_id,
            name=model.name,
            version=model.current_version,
            definition=WorkflowDefinition.model_validate(current.definition),
        )

    async def create(
        self,
        *,
        organization_id: UUID,
        name: str,
        definition: WorkflowDefinition,
        created_by: UUID,
    ) -> PersistedWorkflow:
        workflow = WorkflowModel(
            organization_id=organization_id,
            name=name,
            current_version=1,
            created_by=created_by,
        )
        workflow.versions.append(
            WorkflowVersionModel(
                version=1,
                definition=definition.model_dump(mode="json"),
                created_by=created_by,
            )
        )
        self._session.add(workflow)
        await self._session.flush()
        return PersistedWorkflow(
            id=workflow.id,
            organization_id=organization_id,
            name=name,
            version=1,
            definition=definition,
        )

    async def update_definition(
        self,
        *,
        workflow_id: UUID,
        organization_id: UUID,
        definition: WorkflowDefinition,
        updated_by: UUID,
    ) -> PersistedWorkflow:
        query = select(WorkflowModel).where(
            WorkflowModel.id == workflow_id,
            WorkflowModel.organization_id == organization_id,
        )
        workflow = await self._session.scalar(query)
        if workflow is None:
            raise NotFoundError("workflow not found")
        next_version = workflow.current_version + 1
        workflow.current_version = next_version
        workflow.name = definition.name
        workflow.versions.append(
            WorkflowVersionModel(
                version=next_version,
                definition=definition.model_dump(mode="json"),
                created_by=updated_by,
            )
        )
        await self._session.flush()
        return PersistedWorkflow(
            id=workflow.id,
            organization_id=workflow.organization_id,
            name=workflow.name,
            version=next_version,
            definition=definition.model_copy(update={"version": next_version}),
        )


class SqlAlchemyAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, event: AuditEvent) -> None:
        self._session.add(
            AuditEventModel(
                id=event.id,
                organization_id=event.organization_id,
                actor_id=event.actor_id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                event_metadata=event.metadata,
                created_at=event.created_at,
            )
        )
