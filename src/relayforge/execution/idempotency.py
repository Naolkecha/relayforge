from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    key: str
    value: Any


class IdempotencyStore(Protocol):
    async def get(self, key: str) -> IdempotencyRecord | None: ...

    async def put_if_absent(self, key: str, value: Any) -> bool: ...


class MemoryIdempotencyStore:
    """Deterministic test/local implementation with atomic writes within one process."""

    def __init__(self) -> None:
        self._values: dict[str, IdempotencyRecord] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> IdempotencyRecord | None:
        async with self._lock:
            return self._values.get(key)

    async def put_if_absent(self, key: str, value: Any) -> bool:
        async with self._lock:
            if key in self._values:
                return False
            self._values[key] = IdempotencyRecord(key=key, value=value)
            return True
