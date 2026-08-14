from __future__ import annotations

import time
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from relayforge.errors import AuthenticationError, SecurityPolicyError
from relayforge.security.passwords import hash_password, password_needs_rehash, verify_password
from relayforge.security.secrets import SecretCipher
from relayforge.security.tokens import TokenService, generate_api_key, hash_api_key
from relayforge.security.webhooks import sign_webhook, verify_webhook


def token_service() -> TokenService:
    return TokenService(
        secret="x" * 64,
        access_ttl_seconds=900,
        refresh_ttl_seconds=3600,
    )


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct horse battery staple")
    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("incorrect password", encoded)


def test_short_password_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 12"):
        hash_password("too-short")


def test_malformed_password_hash_fails_closed() -> None:
    assert not verify_password("anything", "not-an-argon2-hash")
    assert password_needs_rehash("not-an-argon2-hash")


def test_access_token_round_trip() -> None:
    user_id = uuid4()
    organization_id = uuid4()
    pair = token_service().issue_pair(user_id, organization_id)
    payload = token_service().decode(pair.access_token, "access")
    assert payload["sub"] == str(user_id)
    assert payload["org"] == str(organization_id)
    assert payload["kind"] == "access"


def test_refresh_token_cannot_be_used_as_access_token() -> None:
    pair = token_service().issue_pair(uuid4(), uuid4())
    with pytest.raises(AuthenticationError, match="unexpected token kind"):
        token_service().decode(pair.refresh_token, "access")


def test_tampered_token_is_rejected() -> None:
    pair = token_service().issue_pair(uuid4(), uuid4())
    tampered = pair.access_token[:-2] + "xx"
    with pytest.raises(AuthenticationError, match="invalid or expired"):
        token_service().decode(tampered, "access")


def test_api_keys_are_random_and_only_hash_is_persistable() -> None:
    raw_a, digest_a = generate_api_key()
    raw_b, digest_b = generate_api_key()
    assert raw_a.startswith("rf_")
    assert raw_a != raw_b
    assert digest_a != digest_b
    assert hash_api_key(raw_a) == digest_a
    assert raw_a not in digest_a


def test_secret_cipher_round_trip() -> None:
    cipher = SecretCipher(Fernet.generate_key().decode())
    encrypted = cipher.encrypt("super-sensitive")
    assert "super-sensitive" not in encrypted
    assert cipher.decrypt(encrypted) == "super-sensitive"


def test_secret_cipher_rejects_tampered_ciphertext() -> None:
    cipher = SecretCipher(Fernet.generate_key().decode())
    encrypted = cipher.encrypt("secret")
    with pytest.raises(SecurityPolicyError):
        cipher.decrypt(encrypted[:-3] + "abc")


def test_webhook_signature_round_trip() -> None:
    timestamp = int(time.time())
    body = b'{"event":"workflow.completed"}'
    signature = sign_webhook("shared-secret", body, timestamp)
    verify_webhook(
        secret="shared-secret",
        body=body,
        timestamp=timestamp,
        signature=signature,
        now=timestamp,
    )


def test_webhook_signature_rejects_tampering() -> None:
    timestamp = 1_700_000_000
    signature = sign_webhook("shared-secret", b"original", timestamp)
    with pytest.raises(AuthenticationError, match="invalid webhook signature"):
        verify_webhook(
            secret="shared-secret",
            body=b"tampered",
            timestamp=timestamp,
            signature=signature,
            now=timestamp,
        )


def test_webhook_replay_window_is_enforced() -> None:
    timestamp = 1_700_000_000
    signature = sign_webhook("shared-secret", b"body", timestamp)
    with pytest.raises(AuthenticationError, match="outside tolerance"):
        verify_webhook(
            secret="shared-secret",
            body=b"body",
            timestamp=timestamp,
            signature=signature,
            now=timestamp + 301,
            tolerance_seconds=300,
        )
