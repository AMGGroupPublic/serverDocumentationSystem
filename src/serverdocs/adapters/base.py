"""Adapter contract — one per supported runtime (lxd, docker, ...)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..model import Entity
from ..transport.base import SSHTransport


class Adapter(ABC):
    """Discover entities on a single host via an SSH transport."""

    #: Short name used in folder paths (e.g. ``"lxd"``, ``"docker"``).
    name: str = ""

    #: Binary that must be present on the remote for this adapter to run.
    probe_binary: str = ""

    def __init__(self, host: str) -> None:
        self.host = host

    async def applies(self, transport: SSHTransport) -> bool:
        """Default check: the probe binary exists on the remote host."""
        if not self.probe_binary:
            return False
        return await transport.which(self.probe_binary)

    @abstractmethod
    async def discover(self, transport: SSHTransport) -> list[Entity]:
        """Return all entities of this type on the host."""
