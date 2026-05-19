"""Tests for the known_hosts helper and ``serverdocs trust`` CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

from serverdocs.__main__ import cli
from serverdocs.store import known_hosts as kh

_FAKE_KEYS_DEV001 = [
    "dev001.example.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIxxxx",
    "dev001.example.com ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABxxxx",
]
_FAKE_KEYS_DEV002 = [
    "dev002.example.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIyyyy",
]


# ---------------------------------------------------------------- unit


def test_update_known_hosts_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "kh"
    added, skipped = kh.update_known_hosts(path, _FAKE_KEYS_DEV001)
    assert (added, skipped) == (2, 0)
    body = path.read_text()
    assert _FAKE_KEYS_DEV001[0] in body
    assert _FAKE_KEYS_DEV001[1] in body
    assert body.endswith("\n")


def test_update_known_hosts_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "kh"
    kh.update_known_hosts(path, _FAKE_KEYS_DEV001)
    added, skipped = kh.update_known_hosts(path, _FAKE_KEYS_DEV001)
    assert (added, skipped) == (0, 2)


def test_update_known_hosts_appends_new_keys(tmp_path: Path) -> None:
    path = tmp_path / "kh"
    kh.update_known_hosts(path, _FAKE_KEYS_DEV001)
    added, skipped = kh.update_known_hosts(path, _FAKE_KEYS_DEV002)
    assert (added, skipped) == (1, 0)
    body = path.read_text()
    assert _FAKE_KEYS_DEV002[0] in body
    assert _FAKE_KEYS_DEV001[0] in body


def test_update_known_hosts_handles_missing_trailing_newline(tmp_path: Path) -> None:
    path = tmp_path / "kh"
    path.write_text("preexisting host ssh-rsa AAAA")  # no newline
    added, _ = kh.update_known_hosts(path, _FAKE_KEYS_DEV001)
    assert added == 2
    lines = path.read_text().splitlines()
    assert lines[0] == "preexisting host ssh-rsa AAAA"
    assert _FAKE_KEYS_DEV001[0] in lines


def test_trust_host_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kh, "fetch_host_keys", lambda host, **_: _FAKE_KEYS_DEV001)
    kh_path = tmp_path / "kh"
    res = kh.trust_host("dev001.example.com", kh_path)
    assert res.ok
    assert res.added == 2
    assert kh_path.exists()


def test_trust_host_no_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kh, "fetch_host_keys", lambda host, **_: [])
    res = kh.trust_host("unreachable", tmp_path / "kh")
    assert not res.ok
    assert "unreachable" in res.error or "no keys" in res.error  # type: ignore[operator]


def test_trust_host_keyscan_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: Any, **__: Any) -> list[str]:
        raise kh.KeyscanError("ssh-keyscan not found on PATH")

    monkeypatch.setattr(kh, "fetch_host_keys", boom)
    res = kh.trust_host("h", tmp_path / "kh")
    assert not res.ok
    assert "ssh-keyscan" in (res.error or "")


# ---------------------------------------------------------------- CLI


def _write_cfg(tmp: Path) -> Path:
    cfg = {
        "output_dir": str(tmp / "out"),
        "ssh_keys_dir": str(tmp / "keys"),
        "known_hosts": str(tmp / "kh"),
        "git": {"enabled": False},
        "servers": [
            {"name": "dev001", "hostname": "dev001.example.com", "user": "root", "keyfile": "k"},
            {"name": "dev002", "hostname": "dev002.example.com", "user": "root", "keyfile": "k"},
        ],
    }
    p = tmp / "servers.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p


def test_cli_trust_explicit_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "serverdocs.__main__.trust_host",
        lambda host, kh_path, **_: kh.TrustResult(host=host, added=2, skipped=0),
    )
    cfg = _write_cfg(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["trust", "--config", str(cfg), "dev001.example.com"])
    assert result.exit_code == 0
    assert "dev001.example.com: added 2" in result.output


def test_cli_trust_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake(host: str, kh_path: Path, **_: Any) -> kh.TrustResult:
        seen.append(host)
        return kh.TrustResult(host=host, added=1)

    monkeypatch.setattr("serverdocs.__main__.trust_host", fake)
    cfg = _write_cfg(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["trust", "--config", str(cfg), "--all"])
    assert result.exit_code == 0
    assert seen == ["dev001.example.com", "dev002.example.com"]


def test_cli_trust_requires_target(tmp_path: Path) -> None:
    cfg = _write_cfg(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["trust", "--config", str(cfg)])
    assert result.exit_code != 0


def test_cli_trust_rejects_both(tmp_path: Path) -> None:
    cfg = _write_cfg(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["trust", "--config", str(cfg), "--all", "h"])
    assert result.exit_code != 0


def test_cli_trust_failure_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "serverdocs.__main__.trust_host",
        lambda host, kh_path, **_: kh.TrustResult(host=host, error="unreachable"),
    )
    cfg = _write_cfg(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["trust", "--config", str(cfg), "dead.example.com"])
    assert result.exit_code == 1
    assert "FAILED" in result.output
