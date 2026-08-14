"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
import secrets

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Secrets are intentionally environment-backed. No production credential belongs in source control.
    """

    model_config = SettingsConfigDict(
        env_prefix="RELAYFORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://relayforge:relayforge@localhost:5432/relayforge"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(48), min_length=32, repr=False)
    encryption_key: str | None = None
    access_token_ttl_seconds: int = Field(default=900, ge=60, le=86_400)
    refresh_token_ttl_seconds: int = Field(default=2_592_000, ge=300, le=31_536_000)
    log_level: str = "INFO"
    block_private_networks: bool = True
    allowed_http_hosts: tuple[str, ...] = ()
    max_workflow_steps: int = Field(default=100, ge=1, le=1_000)
    max_http_response_bytes: int = Field(default=1_048_576, ge=1_024, le=10_485_760)

    @field_validator("allowed_http_hosts", mode="before")
    @classmethod
    def parse_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip().lower() for part in value.split(",") if part.strip())
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalized = value.upper()
        if normalized not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return normalized

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate_production_safety(self) -> None:
        """Fail fast when known development defaults leak into production."""

        if not self.is_production:
            return
        if "RELAYFORGE_JWT_SECRET" not in __import__("os").environ:
            raise ValueError("production requires RELAYFORGE_JWT_SECRET")
        if not self.encryption_key:
            raise ValueError("production requires RELAYFORGE_ENCRYPTION_KEY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production_safety()
    return settings
