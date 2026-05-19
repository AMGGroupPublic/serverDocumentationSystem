"""LXD adapter — parses ``lxc list --format json``.

That single command returns instance config, devices, and runtime state in one shot,
so we don't need a second round-trip per container.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..model import Disk, Entity, Net
from ..transport.base import SSHTransport
from ..units import parse_to_mb
from .base import Adapter

log = logging.getLogger(__name__)


class LXDAdapter(Adapter):
    name = "lxd"
    probe_binary = "lxc"

    async def discover(self, transport: SSHTransport) -> list[Entity]:
        result = await transport.run("lxc list --format json")
        if not result.ok:
            log.warning("%s: lxc list failed: %s", self.host, result.stderr.strip())
            return []
        try:
            instances = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            log.warning("%s: lxc list returned invalid JSON: %s", self.host, exc)
            return []
        return [self._to_entity(i) for i in instances]

    def _to_entity(self, raw: dict[str, Any]) -> Entity:
        config: dict[str, str] = raw.get("config") or {}
        devices: dict[str, dict[str, str]] = raw.get("devices") or {}
        expanded_devices: dict[str, dict[str, str]] = raw.get("expanded_devices") or {}
        state: dict[str, Any] = raw.get("state") or {}

        # Merge devices: expanded_devices include profile-supplied ones too.
        all_devices = {**expanded_devices, **devices}

        cpu = _parse_cpu(config.get("limits.cpu"))
        memory_mb = parse_to_mb(config.get("limits.memory"))

        disks: list[Disk] = []
        for dev_name, dev in all_devices.items():
            if dev.get("type") != "disk":
                continue
            disks.append(
                Disk(
                    name=dev_name,
                    size_mb=parse_to_mb(dev.get("size")),
                    mount=dev.get("path"),
                )
            )

        networks = _extract_networks(state.get("network") or {})

        image = (
            config.get("image.description")
            or _format_image(config)
            or None
        )

        return Entity(
            host=self.host,
            type=self.name,
            name=raw.get("name", "?"),
            state=str(raw.get("status", "?")).lower(),
            cpu=cpu,
            memory_mb=memory_mb,
            disks=disks,
            image=image,
            networks=networks,
            created_at=raw.get("created_at"),
            extra={
                "lxd_type": raw.get("type"),
                "architecture": raw.get("architecture"),
                "profiles": raw.get("profiles"),
            },
        )


def _parse_cpu(raw: str | None) -> int | None:
    if raw is None or raw == "":
        return None
    # `limits.cpu` can be a count ("2") or a pinned set ("0,2,4-6").
    if raw.isdigit():
        return int(raw)
    count = 0
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            try:
                count += int(hi) - int(lo) + 1
            except ValueError:
                continue
        elif part.isdigit():
            count += 1
    return count or None


def _format_image(config: dict[str, str]) -> str | None:
    os_name = config.get("image.os")
    release = config.get("image.release") or config.get("image.version")
    if os_name and release:
        return f"{os_name} {release}"
    return os_name or release


def _extract_networks(network_state: dict[str, Any]) -> list[Net]:
    out: list[Net] = []
    for iface, info in network_state.items():
        if iface == "lo":
            continue
        if not isinstance(info, dict):
            continue
        ipv4 = ipv6 = None
        for addr in info.get("addresses") or []:
            family = addr.get("family")
            scope = addr.get("scope")
            if scope == "link":
                continue
            if family == "inet" and ipv4 is None:
                ipv4 = addr.get("address")
            elif family == "inet6" and ipv6 is None:
                ipv6 = addr.get("address")
        out.append(Net(iface=iface, ipv4=ipv4, ipv6=ipv6, mac=info.get("hwaddr") or None))
    return out
