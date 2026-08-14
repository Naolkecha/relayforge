from __future__ import annotations

import asyncio

import pytest

from relayforge.execution.idempotency import MemoryIdempotencyStore


@pytest.mark.asyncio
async def test_put_if_absent_only_accepts_first_value() -> None:
    store = MemoryIdempotencyStore()
    assert await store.put_if_absent("k", {"winner": 1}) is True
    assert await store.put_if_absent("k", {"winner": 2}) is False
    record = await store.get("k")
    assert record is not None
    assert record.value == {"winner": 1}


@pytest.mark.asyncio
async def test_concurrent_puts_have_single_winner() -> None:
    store = MemoryIdempotencyStore()

    async def put(value: int) -> bool:
        await asyncio.sleep(0)
        return await store.put_if_absent("shared", value)

    results = await asyncio.gather(*(put(index) for index in range(20)))
    assert sum(results) == 1
    assert await store.get("shared") is not None
