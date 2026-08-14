from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from relayforge.config import Settings


def test_allowed_hosts_parse_from_comma_separated_string() -> None:
    settings = Settings(allowed_http_hosts=" api.example.com, hooks.example.com ,, ")
    assert settings.allowed_http_hosts == ("api.example.com", "hooks.example.com")


def test_log_level_is_normalized() -> None:
    assert Settings(log_level="warning").log_level == "WARNING"


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(log_level="LOUD")


def test_production_requires_explicit_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RELAYFORGE_JWT_SECRET", raising=False)
    settings = Settings(environment="production", encryption_key="present")
    with pytest.raises(ValueError, match="JWT"):
        settings.validate_production_safety()


def test_production_requires_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RELAYFORGE_JWT_SECRET", "x" * 40)
    settings = Settings(environment="production", jwt_secret="x" * 40)
    with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
        settings.validate_production_safety()


def test_development_uses_runtime_generated_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RELAYFORGE_JWT_SECRET", raising=False)
    first = Settings().jwt_secret
    second = Settings().jwt_secret
    assert len(first) >= 32
    assert first != second
    assert "development" not in first.lower()
