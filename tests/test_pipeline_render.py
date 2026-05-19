"""Pipeline rendering tests — exercises the render+diff path end-to-end against tmp dirs."""

from __future__ import annotations

from pathlib import Path

from serverdocs.config import Config, DiscoveryConfig, GitConfig, ServerEntry
from serverdocs.model import Entity
from serverdocs.pipeline import HostScan, _render_all


def _config(tmp: Path) -> Config:
    return Config(
        output_dir=tmp / "out",
        ssh_keys_dir=tmp / "keys",
        known_hosts=tmp / "known_hosts",
        metrics_url_template="https://g.example.com/d/{{ host }}?c={{ name }}",
        git=GitConfig(enabled=False),
        discovery=DiscoveryConfig(),
        servers=[
            ServerEntry(name="dev001", hostname="dev001.example.com", user="root", keyfile="k")
        ],
    )


def _entity(name: str = "mymail", typ: str = "docker") -> Entity:
    return Entity(
        host="dev001.example.com",
        type=typ,
        name=name,
        state="running",
        cpu=2,
        memory_mb=512,
        image="postfix:latest",
    )


def test_render_creates_full_tree(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    scans = [HostScan(server=cfg.servers[0], entities=[_entity()])]

    counts = _render_all(cfg, scans, dry_run=False)
    assert counts.created == 1

    base = cfg.output_dir / "servers" / "dev001.example.com" / "docker" / "mymail"
    auto = (base / "AUTO.md").read_text()
    notes = (base / "NOTES.md").read_text()
    index = (cfg.output_dir / "servers" / "dev001.example.com" / "INDEX.md").read_text()
    readme = (cfg.output_dir / "README.md").read_text()

    assert "name: mymail" in auto
    assert "![[servers/dev001.example.com/docker/mymail/AUTO]]" in notes
    assert "https://g.example.com/d/dev001.example.com?c=mymail" in notes
    assert "mymail" in index
    assert "dev001.example.com" in readme


def test_notes_not_overwritten(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    scans = [HostScan(server=cfg.servers[0], entities=[_entity()])]

    _render_all(cfg, scans, dry_run=False)
    notes_path = cfg.output_dir / "servers" / "dev001.example.com" / "docker" / "mymail" / "NOTES.md"
    notes_path.write_text("CUSTOM HUMAN CONTENT")

    _render_all(cfg, scans, dry_run=False)
    assert notes_path.read_text() == "CUSTOM HUMAN CONTENT"


def test_disappeared_entity_listed_in_index(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    # First run with two entities
    scans = [HostScan(server=cfg.servers[0], entities=[_entity("mymail"), _entity("oldsvc")])]
    _render_all(cfg, scans, dry_run=False)

    # Second run with only one — oldsvc disappeared
    scans = [HostScan(server=cfg.servers[0], entities=[_entity("mymail")])]
    counts = _render_all(cfg, scans, dry_run=False)
    assert counts.disappeared == 1

    index = (cfg.output_dir / "servers" / "dev001.example.com" / "INDEX.md").read_text()
    assert "Disappeared" in index
    assert "oldsvc" in index


def test_scan_failure_does_not_count_as_disappeared(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    scans = [HostScan(server=cfg.servers[0], entities=[_entity()])]
    _render_all(cfg, scans, dry_run=False)

    failed = HostScan(server=cfg.servers[0], entities=[], scan_failed=True, error="boom")
    counts = _render_all(cfg, scans=[failed], dry_run=False)
    assert counts.disappeared == 0

    index = (cfg.output_dir / "servers" / "dev001.example.com" / "INDEX.md").read_text()
    assert "Scan failed" in index


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    scans = [HostScan(server=cfg.servers[0], entities=[_entity()])]
    _render_all(cfg, scans, dry_run=True)
    assert not (cfg.output_dir / "servers").exists()
