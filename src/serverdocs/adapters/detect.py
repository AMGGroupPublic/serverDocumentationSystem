"""Probe a host to determine which adapters are applicable."""

from __future__ import annotations

import logging

from ..transport.base import SSHTransport
from .base import Adapter
from .docker import DockerAdapter
from .lxd import LXDAdapter

log = logging.getLogger(__name__)

#: All known adapter classes. Order is the preferred discovery order.
ALL_ADAPTERS: tuple[type[Adapter], ...] = (LXDAdapter, DockerAdapter)


def adapter_by_name(name: str) -> type[Adapter] | None:
    for cls in ALL_ADAPTERS:
        if cls.name == name:
            return cls
    return None


async def detect_adapters(host: str, transport: SSHTransport) -> list[Adapter]:
    """Return instantiated adapters that apply to ``host``."""
    out: list[Adapter] = []
    for cls in ALL_ADAPTERS:
        adapter = cls(host)
        if await adapter.applies(transport):
            log.info("%s: detected %s", host, cls.name)
            out.append(adapter)
    return out
