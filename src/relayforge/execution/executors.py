from __future__ import annotations

import asyncio
from typing import Any, Protocol

import httpx

from relayforge.domain.workflow import ConditionStep, DelayStep, HttpStep, StepDefinition, TransformStep
from relayforge.errors import UpstreamServiceError, WorkflowExecutionError
from relayforge.execution.context import ExecutionContext
from relayforge.security.ssrf import SSRFGuard


class StepExecutor(Protocol):
    async def execute(self, step: StepDefinition, context: ExecutionContext) -> Any: ...


class DefaultStepExecutor:
    def __init__(
        self,
        *,
        ssrf_guard: SSRFGuard,
        http_client: httpx.AsyncClient | None = None,
        max_response_bytes: int = 1_048_576,
    ) -> None:
        self._ssrf = ssrf_guard
        self._client = http_client
        self._max_response_bytes = max_response_bytes

    async def execute(self, step: StepDefinition, context: ExecutionContext) -> Any:
        if isinstance(step, TransformStep):
            return self._transform(step, context)
        if isinstance(step, ConditionStep):
            return self._condition(step, context)
        if isinstance(step, DelayStep):
            await asyncio.sleep(step.seconds)
            return {"slept_seconds": step.seconds}
        if isinstance(step, HttpStep):
            return await self._http(step, context)
        raise WorkflowExecutionError(f"unsupported step type: {type(step).__name__}")

    @staticmethod
    def _transform(step: TransformStep, context: ExecutionContext) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in step.mapping.items():
            output[key] = context.resolve(value) if isinstance(value, str) and value.startswith("$") else value
        return output

    @staticmethod
    def _condition(step: ConditionStep, context: ExecutionContext) -> dict[str, bool]:
        try:
            actual = context.resolve(step.source)
            exists = True
        except (KeyError, IndexError):
            actual = None
            exists = False

        if step.operator == "exists":
            result = exists
        elif not exists:
            result = False
        elif step.operator == "eq":
            result = actual == step.value
        elif step.operator == "ne":
            result = actual != step.value
        elif step.operator == "gt":
            result = actual > step.value
        elif step.operator == "gte":
            result = actual >= step.value
        elif step.operator == "lt":
            result = actual < step.value
        elif step.operator == "lte":
            result = actual <= step.value
        elif step.operator == "contains":
            try:
                result = step.value in actual
            except TypeError as exc:
                raise WorkflowExecutionError("contains requires a container-like source") from exc
        else:  # pragma: no cover - discriminated by Pydantic
            raise WorkflowExecutionError(f"unknown condition operator {step.operator}")
        return {"result": bool(result)}

    async def _http(self, step: HttpStep, context: ExecutionContext) -> dict[str, Any]:
        url = self._render_string(step.url, context)
        await self._ssrf.validate(url)
        headers = {key: self._render_string(value, context) for key, value in step.headers.items()}
        body = self._render_value(step.json_body, context)

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(follow_redirects=False)
        try:
            response = await client.request(step.method, url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(f"HTTP step request failed: {exc.__class__.__name__}") from exc
        finally:
            if owns_client:
                await client.aclose()

        content = response.content
        if len(content) > self._max_response_bytes:
            raise UpstreamServiceError("HTTP response exceeds configured size limit")
        if response.status_code not in step.expected_statuses:
            raise UpstreamServiceError(f"unexpected upstream status {response.status_code}")

        content_type = response.headers.get("content-type", "")
        parsed: Any
        if "application/json" in content_type:
            try:
                parsed = response.json()
            except ValueError:
                parsed = response.text
        else:
            parsed = response.text
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": parsed,
        }

    @staticmethod
    def _render_string(value: str, context: ExecutionContext) -> str:
        if value.startswith("$"):
            return str(context.resolve(value))
        return value

    def _render_value(self, value: Any, context: ExecutionContext) -> Any:
        if isinstance(value, str):
            return context.resolve(value) if value.startswith("$") else value
        if isinstance(value, list):
            return [self._render_value(item, context) for item in value]
        if isinstance(value, dict):
            return {key: self._render_value(item, context) for key, item in value.items()}
        return value
