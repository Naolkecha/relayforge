from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ExecutionContext:
    input: dict[str, Any]
    outputs: dict[str, Any] = field(default_factory=dict)

    def resolve(self, expression: str) -> Any:
        """Resolve a restricted dotted path. No arbitrary Python evaluation is permitted."""

        if expression == "$input":
            return self.input
        if expression.startswith("$input."):
            return _walk(self.input, expression.removeprefix("$input."))
        if expression.startswith("$steps."):
            rest = expression.removeprefix("$steps.")
            step_id, separator, path = rest.partition(".")
            if not step_id:
                raise KeyError("step id is required")
            value = self.outputs[step_id]
            return _walk(value, path) if separator else value
        raise KeyError(f"unsupported expression: {expression}")


def _walk(value: Any, path: str) -> Any:
    current = value
    if not path:
        return current
    for segment in path.split("."):
        if isinstance(current, dict):
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit():
            current = current[int(segment)]
        else:
            raise KeyError(f"cannot resolve segment {segment!r}")
    return current
