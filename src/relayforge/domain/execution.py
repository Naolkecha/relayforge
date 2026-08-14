from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from relayforge.domain.common import ExecutionStatus, StepStatus, new_id, utc_now


@dataclass(slots=True)
class StepRun:
    step_id: str
    status: StepStatus = StepStatus.PENDING
    attempt: int = 0
    output: Any = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(slots=True)
class WorkflowRun:
    workflow_id: UUID
    workflow_version: int
    input: dict[str, Any]
    id: UUID = field(default_factory=new_id)
    status: ExecutionStatus = ExecutionStatus.PENDING
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    steps: dict[str, StepRun] = field(default_factory=dict)
    error: str | None = None

    def start(self) -> None:
        if self.status is not ExecutionStatus.PENDING:
            raise ValueError(f"cannot start execution from {self.status}")
        self.status = ExecutionStatus.RUNNING
        self.started_at = utc_now()

    def succeed(self) -> None:
        if self.status is not ExecutionStatus.RUNNING:
            raise ValueError(f"cannot succeed execution from {self.status}")
        self.status = ExecutionStatus.SUCCEEDED
        self.finished_at = utc_now()

    def fail(self, error: str) -> None:
        if self.status not in {ExecutionStatus.PENDING, ExecutionStatus.RUNNING}:
            raise ValueError(f"cannot fail execution from {self.status}")
        self.status = ExecutionStatus.FAILED
        self.error = error
        self.finished_at = utc_now()
