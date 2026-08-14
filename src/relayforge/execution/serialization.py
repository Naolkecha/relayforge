from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from relayforge.domain.common import ExecutionStatus, StepStatus
from relayforge.domain.execution import StepRun, WorkflowRun


def workflow_run_to_dict(run: WorkflowRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "workflow_id": str(run.workflow_id),
        "workflow_version": run.workflow_version,
        "input": run.input,
        "status": run.status.value,
        "created_at": run.created_at.isoformat(),
        "started_at": _datetime_to_json(run.started_at),
        "finished_at": _datetime_to_json(run.finished_at),
        "error": run.error,
        "steps": {
            step_id: {
                "step_id": state.step_id,
                "status": state.status.value,
                "attempt": state.attempt,
                "output": state.output,
                "error": state.error,
                "started_at": _datetime_to_json(state.started_at),
                "finished_at": _datetime_to_json(state.finished_at),
            }
            for step_id, state in run.steps.items()
        },
    }


def workflow_run_from_dict(data: dict[str, Any]) -> WorkflowRun:
    run = WorkflowRun(
        id=UUID(data["id"]),
        workflow_id=UUID(data["workflow_id"]),
        workflow_version=int(data["workflow_version"]),
        input=dict(data["input"]),
        status=ExecutionStatus(data["status"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        started_at=_datetime_from_json(data.get("started_at")),
        finished_at=_datetime_from_json(data.get("finished_at")),
        error=data.get("error"),
    )
    run.steps = {
        step_id: StepRun(
            step_id=step_data["step_id"],
            status=StepStatus(step_data["status"]),
            attempt=int(step_data["attempt"]),
            output=step_data.get("output"),
            error=step_data.get("error"),
            started_at=_datetime_from_json(step_data.get("started_at")),
            finished_at=_datetime_from_json(step_data.get("finished_at")),
        )
        for step_id, step_data in data.get("steps", {}).items()
    }
    return run


def _datetime_to_json(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _datetime_from_json(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
