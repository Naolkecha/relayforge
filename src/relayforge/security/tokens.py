from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

import jwt

from relayforge.errors import AuthenticationError

TokenKind = Literal["access", "refresh"]


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenService:
    def __init__(
        self,
        *,
        secret: str,
        access_ttl_seconds: int,
        refresh_ttl_seconds: int,
        issuer: str = "relayforge",
    ) -> None:
        if len(secret) < 32:
            raise ValueError("JWT secret must be at least 32 characters")
        self._secret = secret
        self._access_ttl = timedelta(seconds=access_ttl_seconds)
        self._refresh_ttl = timedelta(seconds=refresh_ttl_seconds)
        self._issuer = issuer

    def issue_pair(self, user_id: UUID, organization_id: UUID) -> TokenPair:
        return TokenPair(
            access_token=self._encode(user_id, organization_id, "access", self._access_ttl),
            refresh_token=self._encode(user_id, organization_id, "refresh", self._refresh_ttl),
        )

    def decode(self, token: str, expected_kind: TokenKind) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub", "kind", "org", "jti"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("invalid or expired token") from exc
        if payload.get("kind") != expected_kind:
            raise AuthenticationError("unexpected token kind")
        return payload

    def _encode(
        self,
        user_id: UUID,
        organization_id: UUID,
        kind: TokenKind,
        ttl: timedelta,
    ) -> str:
        now = datetime.now(tz=UTC)
        payload = {
            "sub": str(user_id),
            "org": str(organization_id),
            "kind": kind,
            "jti": str(uuid4()),
            "iat": now,
            "exp": now + ttl,
            "iss": self._issuer,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")


def generate_api_key() -> tuple[str, str]:
    """Return a user-visible API key and a one-way digest safe for persistence."""

    raw = f"rf_{secrets.token_urlsafe(32)}"
    return raw, hash_api_key(raw)


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
