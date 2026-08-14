"""Framework-independent deterministic workflow execution engine."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from relayforge.domain.common import StepStatus, utc_now
from relayforge.domain.execution import StepRun, WorkflowRun
from relayforge.domain.workflow import StepDefinition, WorkflowDefinition
from relayforge.errors import WorkflowExecutionError
from relayforge.execution.context import ExecutionContext
from relayforge.execution.executors import StepExecutor
from relayforge.execution.idempotency import IdempotencyStore

logger = logging.getLogger(__name__)
Sleep = Callable[[float], Awaitable[None]]


class WorkflowEngine:
    def __init__(
        self,
        *,
        executor: StepExecutor,
        idempotency_store: IdempotencyStore,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._executor = executor
        self._idempotency = idempotency_store
        self._sleep = sleep

    async def run(
        self,
        *,
        workflow_id: UUID,
        definition: WorkflowDefinition,
        input_data: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> WorkflowRun:
        order = definition.validated_order()
        cache_key = self._cache_key(workflow_id, definition.version, idempotency_key)
        if cache_key:
            existing = await self._idempotency.get(cache_key)
            if existing is not None:
                return existing.value

        run = WorkflowRun(
            workflow_id=workflow_id,
            workflow_version=definition.version,
            input=input_data,
            steps={step.id: StepRun(step_id=step.id) for step in definition.steps},
        )
        run.start()
        context = ExecutionContext(input=input_data)
        steps = definition.step_map()

        try:
            for step_id in order:
                step = steps[step_id]
                await self._run_step(step, run, context)
            run.succeed()
        except Exception as exc:
            run.fail(str(exc))
            logger.warning(
                "workflow execution failed",
                extra={"execution_id": str(run.id), "workflow_id": str(workflow_id)},
                exc_info=True,
            )

        if cache_key:
            inserted = await self._idempotency.put_if_absent(cache_key, run)
            if not inserted:
                winner = await self._idempotency.get(cache_key)
                if winner is not None:
                    return winner.value
        return run

    async def _run_step(
        self,
        step: StepDefinition,
        run: WorkflowRun,
        context: ExecutionContext,
    ) -> None:
        state = run.steps[step.id]
        state.status = StepStatus.RUNNING
        state.started_at = utc_now()

        last_error: Exception | None = None
        for attempt in range(1, step.retry.max_attempts + 1):
            state.attempt = attempt
            delay = step.retry.delay_for_attempt(attempt)
            if delay:
                await self._sleep(delay)
            try:
                output = await asyncio.wait_for(
                    self._executor.execute(step, context),
                    timeout=step.timeout_seconds,
                )
                state.output = output
                state.status = StepStatus.SUCCEEDED
                state.finished_at = utc_now()
                context.outputs[step.id] = output
                return
            except Exception as exc:
                last_error = exc
                logger.info(
                    "workflow step attempt failed",
                    extra={
                        "execution_id": str(run.id),
                        "step_id": step.id,
                        "attempt": attempt,
                        "max_attempts": step.retry.max_attempts,
                    },
                )

        assert last_error is not None
        state.status = StepStatus.FAILED
        state.error = f"{last_error.__class__.__name__}: {last_error}"
        state.finished_at = utc_now()
        raise WorkflowExecutionError(f"step {step.id!r} failed after {state.attempt} attempt(s)") from last_error

    @staticmethod
    def _cache_key(workflow_id: UUID, version: int, key: str | None) -> str | None:
        if not key:
            return None
        normalized = json.dumps([str(workflow_id), version, key], separators=(",", ":"))
        return f"execution:{hashlib.sha256(normalized.encode()).hexdigest()}"
