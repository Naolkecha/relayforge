from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from relayforge.domain.workflow import (
    ConditionStep,
    DelayStep,
    HttpStep,
    RetryPolicy,
    TransformStep,
    WorkflowDefinition,
)
from relayforge.errors import WorkflowDefinitionError


def workflow(*steps: object) -> WorkflowDefinition:
    return WorkflowDefinition(name="test", steps=steps)


def test_topological_order_respects_dependencies() -> None:
    definition = workflow(
        TransformStep(id="load", name="Load", mapping={"id": "$input.id"}),
        TransformStep(id="shape", name="Shape", depends_on=("load",), mapping={}),
        DelayStep(id="wait", name="Wait", depends_on=("shape",), seconds=0),
    )
    assert definition.validated_order() == ("load", "shape", "wait")


def test_topological_order_is_deterministic_for_independent_steps() -> None:
    definition = workflow(
        DelayStep(id="zeta", name="Z", seconds=0),
        DelayStep(id="alpha", name="A", seconds=0),
        DelayStep(id="middle", name="M", seconds=0),
    )
    assert definition.validated_order() == ("alpha", "middle", "zeta")


def test_missing_dependency_is_rejected() -> None:
    definition = workflow(
        DelayStep(id="ship", name="Ship", depends_on=("charge",), seconds=0),
    )
    with pytest.raises(WorkflowDefinitionError, match="unknown dependencies"):
        definition.validated_order()


def test_cycle_is_rejected() -> None:
    definition = workflow(
        DelayStep(id="a", name="A", depends_on=("c",), seconds=0),
        DelayStep(id="b", name="B", depends_on=("a",), seconds=0),
        DelayStep(id="c", name="C", depends_on=("b",), seconds=0),
    )
    with pytest.raises(WorkflowDefinitionError, match="cycle"):
        definition.validated_order()


def test_duplicate_step_ids_are_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="duplicate step ids"):
        workflow(
            DelayStep(id="same", name="One", seconds=0),
            DelayStep(id="same", name="Two", seconds=0),
        )


def test_duplicate_dependencies_are_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="duplicates"):
        DelayStep(id="a", name="A", depends_on=("x", "x"), seconds=0)


def test_invalid_step_identifier_is_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        DelayStep(id="1 starts badly", name="Bad", seconds=0)


def test_retry_policy_backoff_is_capped() -> None:
    retry = RetryPolicy(
        max_attempts=6,
        initial_delay_seconds=1,
        multiplier=3,
        max_delay_seconds=5,
    )
    assert retry.delay_for_attempt(1) == 0
    assert retry.delay_for_attempt(2) == 1
    assert retry.delay_for_attempt(3) == 3
    assert retry.delay_for_attempt(4) == 5
    assert retry.delay_for_attempt(6) == 5


def test_http_step_disallows_unsupported_method() -> None:
    with pytest.raises(PydanticValidationError):
        HttpStep(id="call", name="Call", method="TRACE", url="https://example.com")


def test_definition_parses_discriminated_step_types() -> None:
    raw = {
        "name": "mixed",
        "steps": [
            {"id": "a", "name": "A", "type": "transform", "mapping": {"x": 1}},
            {
                "id": "b",
                "name": "B",
                "type": "condition",
                "depends_on": ["a"],
                "source": "$steps.a.x",
                "operator": "eq",
                "value": 1,
            },
            {"id": "c", "name": "C", "type": "delay", "depends_on": ["b"], "seconds": 0},
        ],
    }
    definition = WorkflowDefinition.model_validate(raw)
    assert isinstance(definition.steps[0], TransformStep)
    assert isinstance(definition.steps[1], ConditionStep)
    assert isinstance(definition.steps[2], DelayStep)
