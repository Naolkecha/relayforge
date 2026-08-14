from __future__ import annotations

import httpx
import pytest

from relayforge.domain.workflow import ConditionStep, HttpStep, TransformStep
from relayforge.errors import UpstreamServiceError, WorkflowExecutionError
from relayforge.execution.context import ExecutionContext
from relayforge.execution.executors import DefaultStepExecutor
from relayforge.security.ssrf import SSRFGuard


async def public_resolver(host: str, port: int) -> set[str]:
    del host, port
    return {"93.184.216.34"}


def executor(transport: httpx.AsyncBaseTransport | None = None, max_bytes: int = 1024) -> DefaultStepExecutor:
    client = httpx.AsyncClient(transport=transport) if transport else httpx.AsyncClient()
    return DefaultStepExecutor(
        ssrf_guard=SSRFGuard(resolver=public_resolver),
        http_client=client,
        max_response_bytes=max_bytes,
    )


@pytest.mark.asyncio
async def test_transform_resolves_paths_and_literals() -> None:
    service = executor()
    step = TransformStep(
        id="shape",
        name="Shape",
        mapping={"user": "$input.user.name", "count": 2, "enabled": True},
    )
    result = await service.execute(step, ExecutionContext(input={"user": {"name": "Naol"}}))
    assert result == {"user": "Naol", "count": 2, "enabled": True}
    await service._client.aclose()  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("operator", "actual", "expected", "result"),
    [
        ("eq", 5, 5, True),
        ("ne", 5, 4, True),
        ("gt", 5, 4, True),
        ("gte", 5, 5, True),
        ("lt", 4, 5, True),
        ("lte", 5, 5, True),
        ("contains", ["a", "b"], "b", True),
        ("eq", "x", "y", False),
    ],
)
@pytest.mark.asyncio
async def test_condition_operators(operator: str, actual: object, expected: object, result: bool) -> None:
    service = executor()
    step = ConditionStep(
        id="check",
        name="Check",
        source="$input.value",
        operator=operator,  # type: ignore[arg-type]
        value=expected,
    )
    output = await service.execute(step, ExecutionContext(input={"value": actual}))
    assert output == {"result": result}
    await service._client.aclose()  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_exists_condition_handles_missing_path() -> None:
    service = executor()
    step = ConditionStep(id="check", name="Check", source="$input.missing", operator="exists")
    output = await service.execute(step, ExecutionContext(input={}))
    assert output == {"result": False}
    await service._client.aclose()  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_contains_rejects_non_container() -> None:
    service = executor()
    step = ConditionStep(
        id="check", name="Check", source="$input.value", operator="contains", value="x"
    )
    with pytest.raises(WorkflowExecutionError, match="container-like"):
        await service.execute(step, ExecutionContext(input={"value": 123}))
    await service._client.aclose()  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_http_step_returns_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == httpx.URL("https://example.com/hooks")
        assert request.headers["x-customer"] == "42"
        return httpx.Response(201, json={"accepted": True}, request=request)

    service = executor(httpx.MockTransport(handler))
    step = HttpStep(
        id="send",
        name="Send",
        method="POST",
        url="https://example.com/hooks",
        headers={"X-Customer": "$input.customer_id"},
        json_body={"name": "$input.name"},
        expected_statuses=(201,),
    )
    result = await service.execute(step, ExecutionContext(input={"customer_id": 42, "name": "Ada"}))
    assert result["status_code"] == 201
    assert result["body"] == {"accepted": True}
    await service._client.aclose()  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_http_step_rejects_unexpected_status() -> None:
    service = executor(httpx.MockTransport(lambda request: httpx.Response(500, request=request)))
    step = HttpStep(id="send", name="Send", url="https://example.com", expected_statuses=(200,))
    with pytest.raises(UpstreamServiceError, match="unexpected upstream status"):
        await service.execute(step, ExecutionContext(input={}))
    await service._client.aclose()  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_http_step_rejects_oversized_response() -> None:
    service = executor(
        httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 20, request=request)),
        max_bytes=10,
    )
    step = HttpStep(id="send", name="Send", url="https://example.com")
    with pytest.raises(UpstreamServiceError, match="size limit"):
        await service.execute(step, ExecutionContext(input={}))
    await service._client.aclose()  # type: ignore[union-attr]
