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
    assert "0.2.15" in result.output


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


# --------------------------------------------------------------- purge-disappeared


def _seed_two_entities(tmp: Path) -> None:
    """Pre-populate two entity dirs under dev001 so purge_disappeared has
    something to look at without needing a real scan."""
    from serverdocs.config import load_config
    from serverdocs.model import Entity
    from serverdocs.pipeline import HostScan, _render_all

    cfg = load_config(_write_config(tmp))
    entities = [
        Entity(host="dev001.example.com", type="docker", name=n, state="running")
        for n in ("alive", "dead")
    ]
    _render_all(cfg, [HostScan(server=cfg.servers[0], entities=entities)], dry_run=False)


def _patch_scan_host(monkeypatch: pytest.MonkeyPatch, seen_entities: list[str]) -> None:
    """Replace scan_host so the CLI returns a scripted set of live entities
    without touching SSH."""
    from serverdocs.config import load_config
    from serverdocs.model import Entity
    from serverdocs.pipeline import HostScan
    import serverdocs.__main__ as cli_module

    async def fake_scan_host(config, host):  # type: ignore[no-untyped-def]
        server = next(s for s in config.servers if s.hostname == host or s.name == host)
        scan = HostScan(
            server=server,
            entities=[
                Entity(host=server.hostname, type="docker", name=n, state="running")
                for n in seen_entities
            ],
        )
        return server, scan

    monkeypatch.setattr(cli_module, "scan_host", fake_scan_host)


def test_purge_disappeared_aborts_without_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_two_entities(tmp_path)
    _patch_scan_host(monkeypatch, seen_entities=["alive"])  # "dead" is disappeared

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["purge-disappeared", "--config", str(tmp_path / "servers.yaml"), "dev001.example.com"],
        input="n\n",
    )
    assert result.exit_code != 0  # click.confirm(abort=True) exits non-zero on 'n'
    # The dir must still be present — nothing was deleted.
    assert (tmp_path / "out" / "servers" / "dev001.example.com" / "docker" / "dead").is_dir()


def test_purge_disappeared_with_yes_flag_deletes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_two_entities(tmp_path)
    _patch_scan_host(monkeypatch, seen_entities=["alive"])

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["purge-disappeared", "-y", "--config", str(tmp_path / "servers.yaml"), "dev001.example.com"],
    )
    assert result.exit_code == 0, result.output
    assert "removed 1 entity" in result.output
    assert not (tmp_path / "out" / "servers" / "dev001.example.com" / "docker" / "dead").exists()
    assert (tmp_path / "out" / "servers" / "dev001.example.com" / "docker" / "alive").is_dir()


def test_purge_disappeared_no_disappeared_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_two_entities(tmp_path)
    # Live scan sees both — nothing is disappeared.
    _patch_scan_host(monkeypatch, seen_entities=["alive", "dead"])

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["purge-disappeared", "-y", "--config", str(tmp_path / "servers.yaml"), "dev001.example.com"],
    )
    assert result.exit_code == 0
    assert "no disappeared entities" in result.output
    assert (tmp_path / "out" / "servers" / "dev001.example.com" / "docker" / "dead").is_dir()


def test_purge_disappeared_unknown_host_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_two_entities(tmp_path)
    # Don't bother patching — the unknown-host check fires before scan_host runs.

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["purge-disappeared", "-y", "--config", str(tmp_path / "servers.yaml"), "not-in-config.example.com"],
    )
    assert result.exit_code == 2
    assert "host not in config" in result.output
