from __future__ import annotations

from uuid import uuid4

from relayforge.domain.common import StepStatus
from relayforge.domain.execution import StepRun, WorkflowRun
from relayforge.execution.serialization import workflow_run_from_dict, workflow_run_to_dict


def test_workflow_run_serialization_round_trip() -> None:
    run = WorkflowRun(workflow_id=uuid4(), workflow_version=3, input={"customer": 42})
    run.start()
    run.steps["shape"] = StepRun(
        step_id="shape",
        status=StepStatus.SUCCEEDED,
        attempt=1,
        output={"ok": True},
        started_at=run.started_at,
        finished_at=run.started_at,
    )
    run.succeed()

    restored = workflow_run_from_dict(workflow_run_to_dict(run))
    assert restored.id == run.id
    assert restored.workflow_id == run.workflow_id
    assert restored.workflow_version == 3
    assert restored.status == run.status
    assert restored.input == {"customer": 42}
    assert restored.steps["shape"].status is StepStatus.SUCCEEDED
    assert restored.steps["shape"].output == {"ok": True}
    assert restored.finished_at == run.finished_at
