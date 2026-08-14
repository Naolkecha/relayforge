"""Network destination validation for user-configured HTTP workflow steps."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from relayforge.errors import SecurityPolicyError

Resolver = Callable[[str, int], Awaitable[set[str]]]


async def default_resolver(host: str, port: int) -> set[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return {item[4][0] for item in infos}


class SSRFGuard:
    def __init__(
        self,
        *,
        block_private_networks: bool = True,
        allowed_hosts: tuple[str, ...] = (),
        resolver: Resolver = default_resolver,
    ) -> None:
        self._block_private = block_private_networks
        self._allowed_hosts = {host.lower().rstrip(".") for host in allowed_hosts}
        self._resolver = resolver

    async def validate(self, url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            raise SecurityPolicyError("only http and https URLs are allowed")
        if not parsed.hostname:
            raise SecurityPolicyError("URL must include a hostname")
        if parsed.username or parsed.password:
            raise SecurityPolicyError("credentials in URLs are not allowed")

        host = parsed.hostname.lower().rstrip(".")
        if self._allowed_hosts and host not in self._allowed_hosts:
            raise SecurityPolicyError(f"host {host!r} is not in the configured allowlist")

        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = await self._resolver(host, port)
        if not addresses:
            raise SecurityPolicyError("hostname resolved to no addresses")
        if self._block_private:
            for raw in addresses:
                if self._is_forbidden_address(raw):
                    raise SecurityPolicyError(f"destination resolves to forbidden address {raw}")

    @staticmethod
    def _is_forbidden_address(raw: str) -> bool:
        ip = ipaddress.ip_address(raw)
        return any(
            (
                ip.is_private,
                ip.is_loopback,
                ip.is_link_local,
                ip.is_multicast,
                ip.is_reserved,
                ip.is_unspecified,
            )
        )
