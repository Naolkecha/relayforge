from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class Job:
    kind: str
    payload: dict[str, Any]


class JobQueue(Protocol):
    async def enqueue(self, job: Job) -> None: ...

    async def dequeue(self, timeout_seconds: int = 5) -> Job | None: ...
