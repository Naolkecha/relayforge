from __future__ import annotations

import json

from redis.asyncio import Redis

from relayforge.execution.idempotency import IdempotencyRecord
from relayforge.execution.serialization import workflow_run_from_dict, workflow_run_to_dict


class RedisExecutionIdempotencyStore:
    """Distributed completed-execution idempotency backed by Redis SET NX."""

    def __init__(self, redis: Redis, ttl_seconds: int = 86_400) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def get(self, key: str) -> IdempotencyRecord | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        value = workflow_run_from_dict(json.loads(raw))
        return IdempotencyRecord(key=key, value=value)

    async def put_if_absent(self, key: str, value: object) -> bool:
        payload = json.dumps(workflow_run_to_dict(value), separators=(",", ":"), default=str)  # type: ignore[arg-type]
        inserted = await self._redis.set(key, payload, ex=self._ttl_seconds, nx=True)
        return bool(inserted)
