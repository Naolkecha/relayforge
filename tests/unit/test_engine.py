from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from relayforge.domain.common import ExecutionStatus, StepStatus
from relayforge.domain.workflow import DelayStep, RetryPolicy, TransformStep, WorkflowDefinition
from relayforge.execution.context import ExecutionContext
from relayforge.execution.engine import WorkflowEngine
from relayforge.execution.idempotency import MemoryIdempotencyStore


class RecordingExecutor:
    def __init__(self, *, fail_times: int = 0) -> None:
        self.calls: list[str] = []
        self.fail_times = fail_times
        self.attempts = 0

    async def execute(self, step: object, context: ExecutionContext) -> Any:
        step_id = step.id  # type: ignore[attr-defined]
        self.calls.append(step_id)
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise RuntimeError("temporary failure")
        return {"step": step_id, "input": context.input.get("value")}


@pytest.mark.asyncio
async def test_engine_executes_in_dependency_order() -> None:
    executor = RecordingExecutor()
    engine = WorkflowEngine(executor=executor, idempotency_store=MemoryIdempotencyStore())
    definition = WorkflowDefinition(
        name="ordered",
        steps=(
            DelayStep(id="c", name="C", depends_on=("b",), seconds=0),
            DelayStep(id="a", name="A", seconds=0),
            DelayStep(id="b", name="B", depends_on=("a",), seconds=0),
        ),
    )
    run = await engine.run(workflow_id=uuid4(), definition=definition, input_data={"value": 7})
    assert run.status is ExecutionStatus.SUCCEEDED
    assert executor.calls == ["a", "b", "c"]
    assert all(step.status is StepStatus.SUCCEEDED for step in run.steps.values())


@pytest.mark.asyncio
async def test_engine_retries_then_succeeds() -> None:
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    executor = RecordingExecutor(fail_times=2)
    engine = WorkflowEngine(
        executor=executor,
        idempotency_store=MemoryIdempotencyStore(),
        sleep=fake_sleep,
    )
    definition = WorkflowDefinition(
        name="retry",
        steps=(
            TransformStep(
                id="call",
                name="Call",
                mapping={},
                retry=RetryPolicy(
                    max_attempts=3,
                    initial_delay_seconds=0.5,
                    multiplier=2,
                    max_delay_seconds=5,
                ),
            ),
        ),
    )
    run = await engine.run(workflow_id=uuid4(), definition=definition, input_data={})
    assert run.status is ExecutionStatus.SUCCEEDED
    assert run.steps["call"].attempt == 3
    assert delays == [0.5, 1.0]


@pytest.mark.asyncio
async def test_engine_marks_run_failed_after_retry_exhaustion() -> None:
    executor = RecordingExecutor(fail_times=5)
    engine = WorkflowEngine(executor=executor, idempotency_store=MemoryIdempotencyStore())
    definition = WorkflowDefinition(
        name="failure",
        steps=(
            TransformStep(
                id="call",
                name="Call",
                mapping={},
                retry=RetryPolicy(max_attempts=2, initial_delay_seconds=0),
            ),
        ),
    )
    run = await engine.run(workflow_id=uuid4(), definition=definition, input_data={})
    assert run.status is ExecutionStatus.FAILED
    assert run.steps["call"].status is StepStatus.FAILED
    assert run.steps["call"].attempt == 2
    assert "failed after 2 attempt" in (run.error or "")


@pytest.mark.asyncio
async def test_engine_stops_after_first_failed_step() -> None:
    executor = RecordingExecutor(fail_times=10)
    engine = WorkflowEngine(executor=executor, idempotency_store=MemoryIdempotencyStore())
    definition = WorkflowDefinition(
        name="stop",
        steps=(
            TransformStep(id="a", name="A", mapping={}),
            TransformStep(id="b", name="B", depends_on=("a",), mapping={}),
        ),
    )
    run = await engine.run(workflow_id=uuid4(), definition=definition, input_data={})
    assert run.status is ExecutionStatus.FAILED
    assert run.steps["a"].status is StepStatus.FAILED
    assert run.steps["b"].status is StepStatus.PENDING


@pytest.mark.asyncio
async def test_idempotency_reuses_completed_execution() -> None:
    workflow_id = uuid4()
    executor = RecordingExecutor()
    engine = WorkflowEngine(executor=executor, idempotency_store=MemoryIdempotencyStore())
    definition = WorkflowDefinition(
        name="once",
        steps=(TransformStep(id="a", name="A", mapping={}),),
    )
    first = await engine.run(
        workflow_id=workflow_id,
        definition=definition,
        input_data={},
        idempotency_key="request-123",
    )
    second = await engine.run(
        workflow_id=workflow_id,
        definition=definition,
        input_data={"ignored": True},
        idempotency_key="request-123",
    )
    assert second is first
    assert executor.calls == ["a"]


@pytest.mark.asyncio
async def test_same_idempotency_key_is_scoped_by_workflow() -> None:
    executor = RecordingExecutor()
    engine = WorkflowEngine(executor=executor, idempotency_store=MemoryIdempotencyStore())
    definition = WorkflowDefinition(
        name="scope",
        steps=(TransformStep(id="a", name="A", mapping={}),),
    )
    first = await engine.run(
        workflow_id=uuid4(), definition=definition, input_data={}, idempotency_key="same"
    )
    second = await engine.run(
        workflow_id=uuid4(), definition=definition, input_data={}, idempotency_key="same"
    )
    assert first.id != second.id
    assert executor.calls == ["a", "a"]


class SlowExecutor:
    async def execute(self, step: object, context: ExecutionContext) -> Any:
        del step, context
        await asyncio.sleep(0.05)
        return {"ok": True}


@pytest.mark.asyncio
async def test_step_timeout_is_recorded_as_failure() -> None:
    engine = WorkflowEngine(executor=SlowExecutor(), idempotency_store=MemoryIdempotencyStore())
    definition = WorkflowDefinition(
        name="timeout",
        steps=(TransformStep(id="slow", name="Slow", mapping={}, timeout_seconds=0.001),),
    )
    run = await engine.run(workflow_id=uuid4(), definition=definition, input_data={})
    assert run.status is ExecutionStatus.FAILED
    assert run.steps["slow"].status is StepStatus.FAILED
    assert "TimeoutError" in (run.steps["slow"].error or "")
