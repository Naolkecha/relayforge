from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relayforge.config import Settings
from relayforge.domain.common import Role
from relayforge.errors import AuthenticationError, AuthorizationError
from relayforge.infra.db.models import MembershipModel, UserModel
from relayforge.infra.db.session import Database
from relayforge.security.tokens import TokenService

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: UUID
    organization_id: UUID
    role: Role


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> Database:
    return request.app.state.database


async def get_session(database: Database = Depends(get_database)) -> AsyncIterator[AsyncSession]:
    async for session in database.session():
        yield session


def get_token_service(request: Request) -> TokenService:
    return request.app.state.token_service


async def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
    tokens: TokenService = Depends(get_token_service),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("bearer token required")
    payload = tokens.decode(credentials.credentials, "access")
    try:
        user_id = UUID(payload["sub"])
        organization_id = UUID(payload["org"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("invalid token subject") from exc

    membership = await session.scalar(
        select(MembershipModel)
        .join(UserModel, MembershipModel.user_id == UserModel.id)
        .where(
            MembershipModel.user_id == user_id,
            MembershipModel.organization_id == organization_id,
            UserModel.is_active.is_(True),
        )
    )
    if membership is None:
        raise AuthenticationError("membership is no longer active")
    return Principal(user_id=user_id, organization_id=organization_id, role=Role(membership.role))


def require_roles(*roles: Role) -> Callable[..., Principal]:
    async def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in roles:
            raise AuthorizationError("insufficient organization role")
        return principal

    return dependency


def idempotency_key(value: str | None = Header(default=None, alias="Idempotency-Key")) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise ValueError("Idempotency-Key must contain 1 to 200 characters")
    return normalized
