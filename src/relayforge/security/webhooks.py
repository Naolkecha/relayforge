from __future__ import annotations

import hashlib
import hmac
import time

from relayforge.errors import AuthenticationError


def sign_webhook(secret: str, body: bytes, timestamp: int) -> str:
    payload = f"{timestamp}.".encode() + body
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"v1={digest}"


def verify_webhook(
    *,
    secret: str,
    body: bytes,
    timestamp: int,
    signature: str,
    now: int | None = None,
    tolerance_seconds: int = 300,
) -> None:
    current = int(time.time()) if now is None else now
    if abs(current - timestamp) > tolerance_seconds:
        raise AuthenticationError("webhook timestamp outside tolerance")
    expected = sign_webhook(secret, body, timestamp)
    if not hmac.compare_digest(expected, signature):
        raise AuthenticationError("invalid webhook signature")
