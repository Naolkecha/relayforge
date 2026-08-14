from __future__ import annotations

import pytest

from relayforge.errors import SecurityPolicyError
from relayforge.security.ssrf import SSRFGuard


def resolver_for(*addresses: str):
    async def resolver(host: str, port: int) -> set[str]:
        del host, port
        return set(addresses)

    return resolver


@pytest.mark.asyncio
async def test_public_https_destination_is_allowed() -> None:
    guard = SSRFGuard(resolver=resolver_for("93.184.216.34"))
    await guard.validate("https://example.com/path")


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.5.5",
        "192.168.1.10",
        "169.254.169.254",
        "::1",
        "fc00::1",
        "fe80::1",
    ],
)
@pytest.mark.asyncio
async def test_private_and_special_addresses_are_blocked(address: str) -> None:
    guard = SSRFGuard(resolver=resolver_for(address))
    with pytest.raises(SecurityPolicyError, match="forbidden address"):
        await guard.validate("https://example.com")


@pytest.mark.asyncio
async def test_mixed_public_and_private_dns_answers_are_blocked() -> None:
    guard = SSRFGuard(resolver=resolver_for("93.184.216.34", "127.0.0.1"))
    with pytest.raises(SecurityPolicyError):
        await guard.validate("https://example.com")


@pytest.mark.asyncio
async def test_non_http_scheme_is_rejected() -> None:
    guard = SSRFGuard(resolver=resolver_for("93.184.216.34"))
    with pytest.raises(SecurityPolicyError, match="http and https"):
        await guard.validate("file:///etc/passwd")


@pytest.mark.asyncio
async def test_url_credentials_are_rejected() -> None:
    guard = SSRFGuard(resolver=resolver_for("93.184.216.34"))
    with pytest.raises(SecurityPolicyError, match="credentials"):
        await guard.validate("https://user:pass@example.com/private")


@pytest.mark.asyncio
async def test_allowlist_rejects_unknown_host() -> None:
    guard = SSRFGuard(
        allowed_hosts=("api.example.com",),
        resolver=resolver_for("93.184.216.34"),
    )
    with pytest.raises(SecurityPolicyError, match="allowlist"):
        await guard.validate("https://evil.example.net")


@pytest.mark.asyncio
async def test_allowlist_accepts_configured_host_case_insensitively() -> None:
    guard = SSRFGuard(
        allowed_hosts=("API.EXAMPLE.COM",),
        resolver=resolver_for("93.184.216.34"),
    )
    await guard.validate("https://api.example.com/v1")


@pytest.mark.asyncio
async def test_empty_dns_result_is_rejected() -> None:
    guard = SSRFGuard(resolver=resolver_for())
    with pytest.raises(SecurityPolicyError, match="no addresses"):
        await guard.validate("https://example.com")
