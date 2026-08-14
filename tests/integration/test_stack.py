from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("redis")
pytest.importorskip("asyncpg")

from relayforge.config import Settings
from relayforge.main import create_app

pytestmark = pytest.mark.integration


def settings() -> Settings:
    return Settings()


def test_health_checks_reach_postgres_and_redis() -> None:
    with TestClient(create_app(settings())) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json()["checks"] == {"database": "ok", "redis": "ok"}


def test_register_create_and_execute_workflow() -> None:
    with TestClient(create_app(settings())) as client:
        email = "integration-user@example.test"
        registration = client.post(
            "/v1/auth/register",
            json={
                "email": email,
                "password": "integration-password-123",
                "organization_name": "Integration Org",
            },
        )
        assert registration.status_code == 201, registration.text
        payload = registration.json()
        UUID(payload["user_id"])
        UUID(payload["organization_id"])
        token = payload["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        definition = {
            "name": "Welcome workflow",
            "description": "Integration test workflow",
            "steps": [
                {
                    "id": "shape",
                    "name": "Shape payload",
                    "type": "transform",
                    "mapping": {
                        "customer": "$input.customer",
                        "source": "integration-test",
                    },
                }
            ],
        }
        created = client.post("/v1/workflows", headers=headers, json=definition)
        assert created.status_code == 201, created.text
        workflow_id = created.json()["id"]

        executed = client.post(
            f"/v1/workflows/{workflow_id}/execute",
            headers={**headers, "Idempotency-Key": "integration-request-1"},
            json={"input": {"customer": "Ada"}},
        )
        assert executed.status_code == 200, executed.text
        run = executed.json()
        assert run["status"] == "succeeded"
        assert run["steps"]["shape"]["output"] == {
            "customer": "Ada",
            "source": "integration-test",
        }

        repeated = client.post(
            f"/v1/workflows/{workflow_id}/execute",
            headers={**headers, "Idempotency-Key": "integration-request-1"},
            json={"input": {"customer": "Different value"}},
        )
        assert repeated.status_code == 200
        assert repeated.json()["id"] == run["id"]
