"""CLI tests via click's testing harness."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from serverdocs.__main__ import cli


def _write_config(tmp: Path) -> Path:
    cfg = {
        "output_dir": str(tmp / "out"),
        "ssh_keys_dir": str(tmp / "keys"),
        "known_hosts": str(tmp / "known_hosts"),
        "git": {"enabled": False},
        "discovery": {"parallel": 4, "timeout_seconds": 5},
        "servers": [
            {
                "name": "dev001",
                "hostname": "dev001.example.com",
                "user": "root",
                "keyfile": "x",
                "adapters": ["docker"],
            }
        ],
    }
    p = tmp / "servers.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.2.13" in result.output


def test_validate_config_ok(tmp_path: Path) -> None:
    cfg_path = _write_config(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["validate-config", "--config", str(cfg_path)])
    assert result.exit_code == 0
    assert "1 server" in result.output


def test_validate_config_missing_file() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["validate-config", "--config", "/no/such/file"])
    assert result.exit_code != 0


def test_dry_run_emits_no_files(tmp_path: Path) -> None:
    cfg_path = _write_config(tmp_path)
    runner = CliRunner()
    # dry-run will fail to connect (no real host) but should not crash;
    # the host-level failure is logged, not raised.
    result = runner.invoke(cli, ["dry-run", "--config", str(cfg_path)])
    assert result.exit_code == 0
    assert not (tmp_path / "out" / "servers").exists()


def test_config_path_from_envvar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = _write_config(tmp_path)
    monkeypatch.setenv("SERVERDOCS_CONFIG", str(cfg_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["validate-config"])
    assert result.exit_code == 0
    assert "1 server" in result.output


def test_config_default_missing_fails_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SERVERDOCS_CONFIG", raising=False)
    runner = CliRunner()
    # No envvar, no flag → falls back to /config/servers.yaml which doesn't exist
    # on the test host. Click rejects with exit code 2 before our code runs.
    result = runner.invoke(cli, ["validate-config"])
    assert result.exit_code != 0
    assert "/config/servers.yaml" in result.output


def test_run_against_unreachable_host(tmp_path: Path) -> None:
    cfg_path = _write_config(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--config", str(cfg_path)])
    # Pipeline returns 0 even on per-host failure; the failed host is
    # marked stale rather than crashing the whole scan.
    assert result.exit_code == 0
