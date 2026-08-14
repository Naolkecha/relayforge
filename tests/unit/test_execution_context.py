from __future__ import annotations

import pytest

from relayforge.execution.context import ExecutionContext


def test_resolve_entire_input() -> None:
    context = ExecutionContext(input={"customer": {"id": 7}})
    assert context.resolve("$input") == {"customer": {"id": 7}}


def test_resolve_nested_input() -> None:
    context = ExecutionContext(input={"customer": {"profile": {"name": "Ada"}}})
    assert context.resolve("$input.customer.profile.name") == "Ada"


def test_resolve_list_index() -> None:
    context = ExecutionContext(input={"items": [{"sku": "A"}, {"sku": "B"}]})
    assert context.resolve("$input.items.1.sku") == "B"


def test_resolve_step_output() -> None:
    context = ExecutionContext(input={}, outputs={"lookup": {"body": {"id": 42}}})
    assert context.resolve("$steps.lookup.body.id") == 42


def test_resolve_entire_step_output() -> None:
    context = ExecutionContext(input={}, outputs={"lookup": [1, 2, 3]})
    assert context.resolve("$steps.lookup") == [1, 2, 3]


def test_unknown_expression_is_rejected() -> None:
    context = ExecutionContext(input={})
    with pytest.raises(KeyError, match="unsupported expression"):
        context.resolve("__import__('os').system('whoami')")


def test_unknown_mapping_key_is_rejected() -> None:
    context = ExecutionContext(input={"known": 1})
    with pytest.raises(KeyError):
        context.resolve("$input.missing")


def test_non_numeric_list_segment_is_rejected() -> None:
    context = ExecutionContext(input={"items": ["a"]})
    with pytest.raises(KeyError):
        context.resolve("$input.items.first")
