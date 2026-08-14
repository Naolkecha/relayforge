from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from relayforge.api.dependencies import Principal, get_principal, get_session, idempotency_key, require_roles
from relayforge.api.schemas import ExecuteWorkflowRequest, ExecutionResponse, StepRunResponse, WorkflowResponse
from relayforge.application.ports import WorkflowRecord
from relayforge.application.workflows import ExecutionService, WorkflowService
from relayforge.domain.common import Role
from relayforge.domain.workflow import WorkflowDefinition
from relayforge.errors import NotFoundError
from relayforge.infra.repositories.sqlalchemy import SqlAlchemyAuditRepository, SqlAlchemyWorkflowRepository

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _workflow_response(record: WorkflowRecord) -> WorkflowResponse:
    return WorkflowResponse(
        id=record.id,
        organization_id=record.organization_id,
        name=record.name,
        version=record.version,
        definition=record.definition,
    )


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    definition: WorkflowDefinition,
    principal: Principal = Depends(require_roles(Role.OWNER, Role.ADMIN, Role.EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> WorkflowResponse:
    service = WorkflowService(
        workflows=SqlAlchemyWorkflowRepository(session),
        audit=SqlAlchemyAuditRepository(session),
    )
    record = await service.create(
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        definition=definition,
    )
    return _workflow_response(record)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> WorkflowResponse:
    record = await SqlAlchemyWorkflowRepository(session).get(workflow_id, principal.organization_id)
    if record is None:
        raise NotFoundError("workflow not found")
    return _workflow_response(record)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    definition: WorkflowDefinition,
    principal: Principal = Depends(require_roles(Role.OWNER, Role.ADMIN, Role.EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> WorkflowResponse:
    service = WorkflowService(
        workflows=SqlAlchemyWorkflowRepository(session),
        audit=SqlAlchemyAuditRepository(session),
    )
    record = await service.update(
        workflow_id=workflow_id,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        definition=definition,
    )
    return _workflow_response(record)


@router.post("/{workflow_id}/execute", response_model=ExecutionResponse)
async def execute_workflow(
    workflow_id: UUID,
    body: ExecuteWorkflowRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
    key: str | None = Depends(idempotency_key),
) -> ExecutionResponse:
    service = ExecutionService(
        workflows=SqlAlchemyWorkflowRepository(session),
        engine=request.app.state.workflow_engine,
        audit=SqlAlchemyAuditRepository(session),
    )
    run = await service.execute(
        workflow_id=workflow_id,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        input_data=body.input,
        idempotency_key=key,
    )
    return ExecutionResponse(
        id=run.id,
        workflow_id=run.workflow_id,
        workflow_version=run.workflow_version,
        status=run.status.value,
        error=run.error,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        steps={
            step_id: StepRunResponse(
                step_id=step.step_id,
                status=step.status.value,
                attempt=step.attempt,
                output=step.output,
                error=step.error,
                started_at=step.started_at,
                finished_at=step.finished_at,
            )
            for step_id, step in run.steps.items()
        },
    )
