from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relayforge.domain.common import Role
from relayforge.errors import AuthenticationError, ConflictError
from relayforge.infra.db.models import MembershipModel, OrganizationModel, UserModel
from relayforge.security.passwords import hash_password, verify_password
from relayforge.security.tokens import TokenPair, TokenService

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    if not slug:
        raise ValueError("organization name must contain an alphanumeric character")
    return slug[:90]


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    user_id: UUID
    organization_id: UUID
    tokens: TokenPair


class AuthService:
    def __init__(self, session: AsyncSession, tokens: TokenService) -> None:
        self._session = session
        self._tokens = tokens

    async def register(self, *, email: str, password: str, organization_name: str) -> RegistrationResult:
        normalized = normalize_email(email)
        existing = await self._session.scalar(select(UserModel).where(UserModel.email == normalized))
        if existing is not None:
            raise ConflictError("an account with this email already exists")

        base_slug = slugify(organization_name)
        slug = base_slug
        suffix = 1
        while await self._session.scalar(
            select(OrganizationModel.id).where(OrganizationModel.slug == slug)
        ):
            suffix += 1
            slug = f"{base_slug[:84]}-{suffix}"

        user = UserModel(email=normalized, password_hash=hash_password(password))
        organization = OrganizationModel(name=organization_name.strip(), slug=slug)
        self._session.add_all([user, organization])
        await self._session.flush()
        membership = MembershipModel(
            organization_id=organization.id,
            user_id=user.id,
            role=Role.OWNER.value,
        )
        self._session.add(membership)
        await self._session.flush()
        return RegistrationResult(
            user_id=user.id,
            organization_id=organization.id,
            tokens=self._tokens.issue_pair(user.id, organization.id),
        )

    async def login(self, *, email: str, password: str, organization_id: UUID | None = None) -> TokenPair:
        user = await self._session.scalar(
            select(UserModel).where(UserModel.email == normalize_email(email))
        )
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise AuthenticationError("invalid email or password")

        query = select(MembershipModel).where(MembershipModel.user_id == user.id)
        if organization_id is not None:
            query = query.where(MembershipModel.organization_id == organization_id)
        membership = await self._session.scalar(query.order_by(MembershipModel.created_at.asc()))
        if membership is None:
            raise AuthenticationError("user is not a member of the requested organization")
        return self._tokens.issue_pair(user.id, membership.organization_id)

    async def refresh(self, refresh_token: str) -> TokenPair:
        payload = self._tokens.decode(refresh_token, "refresh")
        try:
            user_id = UUID(payload["sub"])
            organization_id = UUID(payload["org"])
        except (KeyError, ValueError) as exc:
            raise AuthenticationError("invalid token subject") from exc

        membership = await self._session.scalar(
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
        return self._tokens.issue_pair(user_id, organization_id)
