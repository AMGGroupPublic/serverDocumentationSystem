"""Docker adapter — ``docker ps -a`` for the list, ``docker inspect`` for details."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..model import Disk, Entity, Net
from ..transport.base import SSHTransport
from ..units import bytes_to_mb
from .base import Adapter

log = logging.getLogger(__name__)


class DockerAdapter(Adapter):
    name = "docker"
    probe_binary = "docker"

    async def discover(self, transport: SSHTransport) -> list[Entity]:
        ps = await transport.run("docker ps -a --no-trunc --format '{{json .}}'")
        if not ps.ok:
            log.warning("%s: docker ps failed: %s", self.host, ps.stderr.strip())
            return []
        ids: list[str] = []
        for line in ps.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = row.get("ID")
            if cid:
                ids.append(cid)
        if not ids:
            return []

        inspect = await transport.run(f"docker inspect {' '.join(ids)}")
        if not inspect.ok:
            log.warning("%s: docker inspect failed: %s", self.host, inspect.stderr.strip())
            return []
        try:
            details = json.loads(inspect.stdout or "[]")
        except json.JSONDecodeError as exc:
            log.warning("%s: docker inspect returned invalid JSON: %s", self.host, exc)
            return []
        return [self._to_entity(d) for d in details]

    def _to_entity(self, raw: dict[str, Any]) -> Entity:
        name = (raw.get("Name") or "").lstrip("/") or raw.get("Id", "?")[:12]
        host_config = raw.get("HostConfig") or {}
        config = raw.get("Config") or {}
        state = raw.get("State") or {}
        network_settings = raw.get("NetworkSettings") or {}

        cpu = _parse_cpu(host_config)
        memory_mb = bytes_to_mb(host_config.get("Memory") or None)

        disks: list[Disk] = []
        for mount in raw.get("Mounts") or []:
            disks.append(
                Disk(
                    name=mount.get("Name") or mount.get("Source") or "?",
                    size_mb=None,  # not available without separate volume inspect
                    mount=mount.get("Destination"),
                )
            )

        networks: list[Net] = []
        for net_name, net_info in (network_settings.get("Networks") or {}).items():
            networks.append(
                Net(
                    iface=net_name,
                    ipv4=net_info.get("IPAddress") or None,
                    ipv6=net_info.get("GlobalIPv6Address") or None,
                    mac=net_info.get("MacAddress") or None,
                )
            )

        return Entity(
            host=self.host,
            type=self.name,
            name=name,
            state=str(state.get("Status") or "?").lower(),
            cpu=cpu,
            memory_mb=memory_mb,
            disks=disks,
            image=config.get("Image"),
            networks=networks,
            created_at=raw.get("Created"),
            extra={
                "id": raw.get("Id", "")[:12],
                "restart_policy": (host_config.get("RestartPolicy") or {}).get("Name"),
                "ports": list((config.get("ExposedPorts") or {}).keys()),
            },
        )


def _parse_cpu(host_config: dict[str, Any]) -> int | None:
    nano = host_config.get("NanoCpus")
    if isinstance(nano, int) and nano > 0:
        return max(1, round(nano / 1_000_000_000))
    cpuset = host_config.get("CpusetCpus")
    if isinstance(cpuset, str) and cpuset:
        count = 0
        for part in cpuset.split(","):
            part = part.strip()
            if "-" in part:
                lo, hi = part.split("-", 1)
                try:
                    count += int(hi) - int(lo) + 1
                except ValueError:
                    continue
            elif part.isdigit():
                count += 1
        if count:
            return count
    return None
