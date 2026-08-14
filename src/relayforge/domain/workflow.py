"""Workflow definition model and graph validation."""

from __future__ import annotations

from collections import deque
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from relayforge.errors import WorkflowDefinitionError


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_attempts: int = Field(default=1, ge=1, le=10)
    initial_delay_seconds: float = Field(default=0.25, ge=0, le=60)
    multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    max_delay_seconds: float = Field(default=30.0, ge=0, le=300)

    def delay_for_attempt(self, attempt: int) -> float:
        if attempt <= 1:
            return 0.0
        raw = self.initial_delay_seconds * (self.multiplier ** (attempt - 2))
        return min(raw, self.max_delay_seconds)


class BaseStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$")
    name: str = Field(min_length=1, max_length=200)
    depends_on: tuple[str, ...] = ()
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    retry: RetryPolicy = RetryPolicy()

    @field_validator("depends_on")
    @classmethod
    def no_duplicate_dependencies(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("depends_on cannot contain duplicates")
        return value


class HttpStep(BaseStep):
    type: Literal["http"] = "http"
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    url: str = Field(min_length=1, max_length=2_048)
    headers: dict[str, str] = Field(default_factory=dict)
    json_body: dict[str, Any] | list[Any] | None = None
    expected_statuses: tuple[int, ...] = (200, 201, 202, 204)


class TransformStep(BaseStep):
    type: Literal["transform"] = "transform"
    mapping: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ConditionStep(BaseStep):
    type: Literal["condition"] = "condition"
    source: str = Field(min_length=1, max_length=500)
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains", "exists"]
    value: Any = None


class DelayStep(BaseStep):
    type: Literal["delay"] = "delay"
    seconds: float = Field(ge=0, le=60)


StepDefinition = Annotated[
    HttpStep | TransformStep | ConditionStep | DelayStep,
    Field(discriminator="type"),
]


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2_000)
    version: int = Field(default=1, ge=1)
    steps: tuple[StepDefinition, ...] = Field(min_length=1, max_length=100)

    @field_validator("steps")
    @classmethod
    def unique_step_ids(cls, steps: tuple[StepDefinition, ...]) -> tuple[StepDefinition, ...]:
        ids = [step.id for step in steps]
        duplicates = sorted({step_id for step_id in ids if ids.count(step_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate step ids: {', '.join(duplicates)}")
        return steps

    def validated_order(self) -> tuple[str, ...]:
        return topological_order(self.steps)

    def step_map(self) -> dict[str, StepDefinition]:
        return {step.id: step for step in self.steps}


def topological_order(steps: tuple[StepDefinition, ...]) -> tuple[str, ...]:
    """Return a deterministic topological order or raise for invalid graphs."""

    step_ids = {step.id for step in steps}
    missing: dict[str, list[str]] = {}
    indegree = {step.id: 0 for step in steps}
    outgoing: dict[str, list[str]] = {step.id: [] for step in steps}

    for step in steps:
        unknown = [dependency for dependency in step.depends_on if dependency not in step_ids]
        if unknown:
            missing[step.id] = unknown
        for dependency in step.depends_on:
            if dependency in step_ids:
                outgoing[dependency].append(step.id)
                indegree[step.id] += 1

    if missing:
        details = "; ".join(f"{step}: {','.join(deps)}" for step, deps in sorted(missing.items()))
        raise WorkflowDefinitionError(f"workflow references unknown dependencies: {details}")

    queue: deque[str] = deque(sorted(step_id for step_id, degree in indegree.items() if degree == 0))
    ordered: list[str] = []

    while queue:
        step_id = queue.popleft()
        ordered.append(step_id)
        for child in sorted(outgoing[step_id]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if len(ordered) != len(steps):
        cycle_members = sorted(step_id for step_id, degree in indegree.items() if degree > 0)
        raise WorkflowDefinitionError(
            f"workflow graph contains a cycle involving: {', '.join(cycle_members)}"
        )
    return tuple(ordered)
