from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from relayforge.domain.workflow import WorkflowDefinition


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    organization_name: str = Field(min_length=2, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    organization_id: UUID | None = None


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegistrationResponse(TokenResponse):
    user_id: UUID
    organization_id: UUID


class WorkflowResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    version: int
    definition: WorkflowDefinition


class ExecuteWorkflowRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


class StepRunResponse(BaseModel):
    step_id: str
    status: str
    attempt: int
    output: Any = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ExecutionResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    workflow_version: int
    status: str
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    steps: dict[str, StepRunResponse]

    model_config = ConfigDict(from_attributes=True)
