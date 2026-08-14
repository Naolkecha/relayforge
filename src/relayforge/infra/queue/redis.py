from __future__ import annotations

import json

from redis.asyncio import Redis

from relayforge.infra.queue.base import Job


class RedisJobQueue:
    def __init__(self, redis: Redis, queue_name: str = "relayforge:jobs") -> None:
        self._redis = redis
        self._queue_name = queue_name

    async def enqueue(self, job: Job) -> None:
        await self._redis.rpush(
            self._queue_name,
            json.dumps({"kind": job.kind, "payload": job.payload}, separators=(",", ":")),
        )

    async def dequeue(self, timeout_seconds: int = 5) -> Job | None:
        result = await self._redis.blpop(self._queue_name, timeout=timeout_seconds)
        if result is None:
            return None
        _, raw = result
        parsed = json.loads(raw)
        return Job(kind=parsed["kind"], payload=parsed["payload"])
