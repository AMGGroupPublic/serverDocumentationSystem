"""Config loader tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from serverdocs.config import Config, load_config


def _example_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "servers.example.yaml"


def test_example_config_loads() -> None:
    cfg = load_config(_example_path())
    assert isinstance(cfg, Config)
    assert cfg.servers
    assert cfg.discovery.parallel >= 1


def test_server_address_prefers_ip(tmp_path: Path) -> None:
    raw = {
        "output_dir": "/tmp/out",
        "ssh_keys_dir": "/keys",
        "known_hosts": "/data/known_hosts",
        "servers": [
            {
                "name": "x",
                "hostname": "x.example.com",
                "ip": "10.0.0.5",
                "user": "root",
                "keyfile": "x",
                "adapters": ["auto"],
            }
        ],
    }
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(raw))
    cfg = load_config(p)
    assert cfg.servers[0].address == "10.0.0.5"


def test_invalid_config_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("servers: not-a-list\n")
    with pytest.raises(Exception):  # noqa: B017 — pydantic raises ValidationError
        load_config(p)
