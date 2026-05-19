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


def test_notes_customisation_column(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    scans = [
        HostScan(
            server=cfg.servers[0],
            entities=[_entity("mymail"), _entity("nginx")],
        )
    ]
    # First run: both notes are scaffold (X / ❌)
    _render_all(cfg, scans, dry_run=False)
    index_first = (cfg.output_dir / "servers" / "dev001.example.com" / "INDEX.md").read_text()
    assert "| ❌ |" in index_first
    assert "✅" not in index_first

    # Human edits mymail's notes
    notes = cfg.output_dir / "servers" / "dev001.example.com" / "docker" / "mymail" / "NOTES.md"
    notes.write_text("# mymail\n\nReal documentation written by a human.\n")

    # Second run: mymail tick, nginx still X
    _render_all(cfg, scans, dry_run=False)
    index_second = (cfg.output_dir / "servers" / "dev001.example.com" / "INDEX.md").read_text()
    mymail_row = next(line for line in index_second.splitlines() if "mymail" in line)
    nginx_row = next(line for line in index_second.splitlines() if "nginx" in line)
    assert "✅" in mymail_row
    assert "❌" in nginx_row


def test_back_links_rendered(tmp_path: Path) -> None:
    """AUTO and host INDEX include explicit back-links so SB navigates with a
    fresh cursor (avoids the table-edit-mode issue from restored cursor pos)."""
    cfg = _config(tmp_path)
    scans = [HostScan(server=cfg.servers[0], entities=[_entity()])]
    _render_all(cfg, scans, dry_run=False)

    auto = (cfg.output_dir / "servers" / "dev001.example.com" / "docker" / "mymail" / "AUTO.md").read_text()
    index = (cfg.output_dir / "servers" / "dev001.example.com" / "INDEX.md").read_text()
    notes = (cfg.output_dir / "servers" / "dev001.example.com" / "docker" / "mymail" / "NOTES.md").read_text()

    # AUTO carries the back link (NOTES picks it up via transclusion).
    assert "[[servers/dev001.example.com/INDEX#dev001.example.com|← Back to dev001.example.com]]" in auto
    # Host INDEX links back to the overview.
    assert "[[README#Server Documentation|← Back to overview]]" in index
    # NOTES scaffold deliberately unchanged so the customization diff stays stable.
    assert "← Back" not in notes


def test_links_use_wikilink_form(tmp_path: Path) -> None:
    """Internal navigation uses SilverBullet [[Page|alias]] wikilinks so SB
    opens the target in the same tab rather than spawning a new one."""
    cfg = _config(tmp_path)
    scans = [HostScan(server=cfg.servers[0], entities=[_entity()])]
    _render_all(cfg, scans, dry_run=False)

    index = (cfg.output_dir / "servers" / "dev001.example.com" / "INDEX.md").read_text()
    readme = (cfg.output_dir / "README.md").read_text()

    assert "[[servers/dev001.example.com/docker/mymail/NOTES|mymail]]" in index
    assert "[[servers/dev001.example.com/INDEX|dev001.example.com]]" in readme

    # No leftover markdown-style internal links pointing at .md files.
    assert "](servers/" not in readme
    assert "/NOTES.md)" not in index


def test_host_index_orders_running_first_then_alpha(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    entities = [
        Entity(host="dev001.example.com", type="docker", name="zeta", state="running"),
        Entity(host="dev001.example.com", type="docker", name="alpha", state="exited"),
        Entity(host="dev001.example.com", type="docker", name="bravo", state="running"),
        Entity(host="dev001.example.com", type="docker", name="ZULU", state="running"),
        Entity(host="dev001.example.com", type="docker", name="charlie", state="stopped"),
    ]
    scans = [HostScan(server=cfg.servers[0], entities=entities)]
    _render_all(cfg, scans, dry_run=False)

    index = (cfg.output_dir / "servers" / "dev001.example.com" / "INDEX.md").read_text()
    # Wikilink form: [[...|alias]] — locate by the |alias]] suffix.
    positions = {n: index.index(f"|{n}]]") for n in ["bravo", "zeta", "ZULU", "alpha", "charlie"]}
    # Running, alpha (case-insensitive): bravo, zeta, ZULU
    assert positions["bravo"] < positions["zeta"] < positions["ZULU"]
    # Then non-running, alpha: alpha, charlie
    assert positions["ZULU"] < positions["alpha"] < positions["charlie"]


def test_concurrent_run_is_skipped(tmp_path: Path) -> None:
    """If another process holds the lock, run() exits 0 without doing work."""
    import asyncio
    import fcntl
    import os

    from serverdocs.pipeline import run as pipeline_run

    cfg = _config(tmp_path)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    # Simulate another process holding the lock.
    lock_path = cfg.output_dir / ".serverdocs.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        # wait_seconds defaults to 5 — patch to keep test fast.
        from serverdocs import pipeline as pl

        original = pl._run_lock

        def quick_lock(out_dir, *, dry_run, wait_seconds=0.2):
            return original(out_dir, dry_run=dry_run, wait_seconds=0.2)

        pl._run_lock = quick_lock  # type: ignore[attr-defined]
        try:
            rc = asyncio.run(pipeline_run(cfg, dry_run=False))
        finally:
            pl._run_lock = original  # type: ignore[attr-defined]
        assert rc == 0
        # No scan happened — no output tree created beyond the lock file.
        assert not (cfg.output_dir / "servers").exists()
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    scans = [HostScan(server=cfg.servers[0], entities=[_entity()])]
    _render_all(cfg, scans, dry_run=True)
    assert not (cfg.output_dir / "servers").exists()
