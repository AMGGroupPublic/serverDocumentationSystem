"""Adapter detection + selection tests."""

from __future__ import annotations

import pytest

from serverdocs.adapters.detect import ALL_ADAPTERS, adapter_by_name, detect_adapters
from serverdocs.config import ServerEntry
from serverdocs.pipeline import _select_adapters

from .conftest import FakeTransport


def test_adapter_by_name() -> None:
    assert adapter_by_name("lxd") is not None
    assert adapter_by_name("docker") is not None
    assert adapter_by_name("nope") is None


def test_all_adapters_have_names() -> None:
    for cls in ALL_ADAPTERS:
        assert cls.name
        assert cls.probe_binary


@pytest.mark.asyncio
async def test_detect_finds_docker_only() -> None:
    transport = FakeTransport()
    transport.seed("command -v lxc", exit_code=1)
    transport.seed("command -v docker", stdout="/usr/bin/docker")
    found = await detect_adapters("h", transport)
    assert [a.name for a in found] == ["docker"]


@pytest.mark.asyncio
async def test_select_adapters_auto() -> None:
    transport = FakeTransport()
    transport.seed("command -v lxc", stdout="/usr/bin/lxc")
    transport.seed("command -v docker", exit_code=1)
    server = ServerEntry(name="x", hostname="x", user="root", keyfile="k", adapters=["auto"])
    out = await _select_adapters(server, transport)
    assert [a.name for a in out] == ["lxd"]


@pytest.mark.asyncio
async def test_select_adapters_explicit_unknown_skipped() -> None:
    server = ServerEntry(
        name="x", hostname="x", user="root", keyfile="k", adapters=["docker"]
    )
    out = await _select_adapters(server, FakeTransport())
    assert [a.name for a in out] == ["docker"]
