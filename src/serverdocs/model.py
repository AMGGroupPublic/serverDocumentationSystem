"""Normalised entity model.

Adapters return ``list[Entity]``; renderers only see ``Entity``.
Adding a new VM/container type means writing one adapter, nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Disk:
    name: str
    size_mb: int | None = None
    mount: str | None = None


@dataclass
class Net:
    iface: str
    ipv4: str | None = None
    ipv6: str | None = None
    mac: str | None = None


@dataclass
class ImportedDoc:
    """A document copied in from outside the doc tree (e.g. a container's
    project README living on the host filesystem)."""

    source_path: str  # absolute host path the content was read from
    content: str


@dataclass
class Entity:
    host: str
    type: str
    name: str
    state: str
    cpu: int | None = None
    memory_mb: int | None = None
    disks: list[Disk] = field(default_factory=list)
    image: str | None = None
    networks: list[Net] = field(default_factory=list)
    created_at: str | None = None
    #: Upstream source repo URL (e.g. OCI ``org.opencontainers.image.source``).
    source_url: str | None = None
    #: A README imported from the host, copied into the entity's doc folder.
    readme: ImportedDoc | None = None
    last_seen: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z")
    extra: dict[str, object] = field(default_factory=dict)

    @property
    def path_parts(self) -> tuple[str, str, str]:
        """Folder layout: servers/<host>/<type>/<name>/"""
        return (self.host, self.type, self.name)
