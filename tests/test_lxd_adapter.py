"""LXD adapter tests."""

from __future__ import annotations

import json

import pytest

from serverdocs.adapters.lxd import LXDAdapter

from .conftest import FakeTransport

_LXC_LIST = json.dumps(
    [
        {
            "name": "mymail",
            "status": "Running",
            "type": "container",
            "architecture": "x86_64",
            "created_at": "2024-01-15T10:30:00Z",
            "profiles": ["default"],
            "config": {
                "image.os": "ubuntu",
                "image.release": "jammy",
                "limits.cpu": "2",
                "limits.memory": "512MB",
            },
            "devices": {
                "root": {"path": "/", "pool": "default", "size": "20GB", "type": "disk"},
            },
            "expanded_devices": {
                "eth0": {"name": "eth0", "nictype": "bridged", "parent": "lxdbr0", "type": "nic"},
                "root": {"path": "/", "pool": "default", "type": "disk"},
            },
            "state": {
                "network": {
                    "lo": {
                        "addresses": [
                            {"family": "inet", "address": "127.0.0.1", "netmask": "8", "scope": "local"}
                        ],
                    },
                    "eth0": {
                        "addresses": [
                            {"family": "inet", "address": "10.0.0.5", "netmask": "24", "scope": "global"},
                            {"family": "inet6", "address": "fe80::1", "netmask": "64", "scope": "link"},
                        ],
                        "hwaddr": "00:16:3e:00:00:05",
                    },
                },
            },
        },
        {
            "name": "stopped-one",
            "status": "Stopped",
            "type": "container",
            "config": {},
            "devices": {},
            "expanded_devices": {},
            "state": {"network": None},
        },
    ]
)


@pytest.mark.asyncio
async def test_lxd_parses_running_container() -> None:
    transport = FakeTransport()
    transport.seed("lxc list", stdout=_LXC_LIST)
    adapter = LXDAdapter("dev001.example.com")

    entities = await adapter.discover(transport)

    assert len(entities) == 2
    mail = next(e for e in entities if e.name == "mymail")
    assert mail.state == "running"
    assert mail.cpu == 2
    assert mail.memory_mb == 512
    assert mail.image == "ubuntu jammy"
    assert mail.created_at == "2024-01-15T10:30:00Z"
    assert any(d.name == "root" and d.size_mb == 20_000 for d in mail.disks)
    eth0 = next(n for n in mail.networks if n.iface == "eth0")
    assert eth0.ipv4 == "10.0.0.5"
    assert eth0.ipv6 is None  # link-local filtered
    assert eth0.mac == "00:16:3e:00:00:05"
    assert all(n.iface != "lo" for n in mail.networks)


@pytest.mark.asyncio
async def test_lxd_handles_stopped() -> None:
    transport = FakeTransport()
    transport.seed("lxc list", stdout=_LXC_LIST)
    adapter = LXDAdapter("dev001.example.com")

    entities = await adapter.discover(transport)
    stopped = next(e for e in entities if e.name == "stopped-one")
    assert stopped.state == "stopped"
    assert stopped.cpu is None
    assert stopped.memory_mb is None
    assert stopped.networks == []


@pytest.mark.asyncio
async def test_lxd_failed_command_returns_empty() -> None:
    transport = FakeTransport()
    transport.seed("lxc list", stderr="boom", exit_code=1)
    adapter = LXDAdapter("dev001.example.com")
    assert await adapter.discover(transport) == []


@pytest.mark.asyncio
async def test_lxd_invalid_json_returns_empty() -> None:
    transport = FakeTransport()
    transport.seed("lxc list", stdout="not json")
    adapter = LXDAdapter("dev001.example.com")
    assert await adapter.discover(transport) == []


@pytest.mark.asyncio
async def test_lxd_cpu_pinned_range() -> None:
    raw = json.dumps(
        [{"name": "x", "status": "Running", "type": "container",
          "config": {"limits.cpu": "0,2,4-6"}, "devices": {}, "state": {}}]
    )
    transport = FakeTransport()
    transport.seed("lxc list", stdout=raw)
    adapter = LXDAdapter("h")
    entities = await adapter.discover(transport)
    assert entities[0].cpu == 5  # 0, 2, 4, 5, 6
