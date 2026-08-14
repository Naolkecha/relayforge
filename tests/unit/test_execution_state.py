from __future__ import annotations

from uuid import uuid4

import pytest

from relayforge.domain.common import ExecutionStatus
from relayforge.domain.execution import WorkflowRun


def new_run() -> WorkflowRun:
    return WorkflowRun(workflow_id=uuid4(), workflow_version=1, input={})


def test_execution_state_happy_path() -> None:
    run = new_run()
    assert run.status is ExecutionStatus.PENDING
    run.start()
    assert run.status is ExecutionStatus.RUNNING
    assert run.started_at is not None
    run.succeed()
    assert run.status is ExecutionStatus.SUCCEEDED
    assert run.finished_at is not None


def test_execution_can_fail_while_pending() -> None:
    run = new_run()
    run.fail("validation failed")
    assert run.status is ExecutionStatus.FAILED
    assert run.error == "validation failed"


def test_execution_cannot_start_twice() -> None:
    run = new_run()
    run.start()
    with pytest.raises(ValueError, match="cannot start"):
        run.start()


def test_execution_cannot_succeed_before_start() -> None:
    with pytest.raises(ValueError, match="cannot succeed"):
        new_run().succeed()


def test_terminal_execution_cannot_fail_again() -> None:
    run = new_run()
    run.start()
    run.succeed()
    with pytest.raises(ValueError, match="cannot fail"):
        run.fail("late error")
