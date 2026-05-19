"""Pipeline: discover → diff → render → commit."""

from __future__ import annotations

import asyncio
import errno
import fcntl
import logging
import os
from contextlib import contextmanager
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from jinja2 import Environment

from .adapters.base import Adapter
from .adapters.detect import adapter_by_name, detect_adapters
from .config import Config, ServerEntry
from .model import Entity
from .render.auto import render_auto
from .render.front_page import render_front_page
from .render.host_index import render_host_index
from .render.notes import render_notes
from .store.git import GitRepo
from .store.tree import TreeStore
from .transport.asyncssh_transport import AsyncSSHTransport, TransportError
from .transport.base import SSHTransport

log = logging.getLogger(__name__)


@dataclass
class HostScan:
    server: ServerEntry
    entities: list[Entity] = field(default_factory=list)
    scan_failed: bool = False
    error: str | None = None
    last_scan: str = field(default_factory=lambda: _now())


@dataclass
class WriteCounts:
    created: int = 0
    updated: int = 0
    disappeared: int = 0


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


async def run(config: Config, *, dry_run: bool = False) -> int:
    log.info("scan starting: %d server(s), dry_run=%s", len(config.servers), dry_run)

    with _run_lock(config.output_dir, dry_run=dry_run) as acquired:
        if not acquired:
            log.warning("another serverdocs scan is in progress — skipping this run")
            return 0
        scans = await _discover_all(config)
        counts = _render_all(config, scans, dry_run=dry_run)
        _commit_if_changed(config, counts, dry_run=dry_run)
    return 0


@contextmanager
def _run_lock(output_dir: Path, *, dry_run: bool, wait_seconds: float = 5.0) -> Iterator[bool]:
    """Process-wide mutex so concurrent serverdocs runs don't race on the tree.

    In dry-run mode the lock is skipped — dry-run touches nothing on disk and
    callers may legitimately want to inspect output while a scan is running.
    """
    if dry_run:
        yield True
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    lock_path = output_dir / ".serverdocs.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        deadline = asyncio.get_event_loop().time() + wait_seconds
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                    raise
                if asyncio.get_event_loop().time() >= deadline:
                    yield False
                    return
                # Cheap polling — flock has no async API in stdlib.
                import time as _time
                _time.sleep(0.25)
        yield True
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


# ---------------------------------------------------------------- discovery


async def _discover_all(config: Config) -> list[HostScan]:
    sem = asyncio.Semaphore(config.discovery.parallel)

    async def scan_one(server: ServerEntry) -> HostScan:
        async with sem:
            return await _scan_server(server, config)

    return await asyncio.gather(*(scan_one(s) for s in config.servers))


async def _scan_server(server: ServerEntry, config: Config) -> HostScan:
    log.info("scanning %s (%s)", server.name, server.address)
    transport = AsyncSSHTransport(
        host=server.address,
        user=server.user,
        keyfile=config.ssh_keys_dir / server.keyfile,
        known_hosts=config.known_hosts,
        timeout=float(config.discovery.timeout_seconds),
        port=server.port,
    )
    scan = HostScan(server=server)
    try:
        async with transport:
            adapters = await _select_adapters(server, transport)
            for adapter in adapters:
                try:
                    scan.entities.extend(await adapter.discover(transport))
                except (TransportError, OSError) as exc:
                    log.warning("%s: adapter %s failed: %s", server.name, adapter.name, exc)
    except TransportError as exc:
        log.warning("%s: %s", server.name, exc)
        scan.scan_failed = True
        scan.error = str(exc)
    return scan


async def _select_adapters(server: ServerEntry, transport: SSHTransport) -> list[Adapter]:
    if server.adapters == ["auto"]:
        return await detect_adapters(server.hostname, transport)
    out: list[Adapter] = []
    for name in server.adapters:
        if name == "auto":
            continue
        cls = adapter_by_name(name)
        if cls is None:
            log.warning("%s: unknown adapter %r — skipping", server.name, name)
            continue
        out.append(cls(server.hostname))
    return out


# ---------------------------------------------------------------- rendering


def _render_all(config: Config, scans: list[HostScan], *, dry_run: bool) -> WriteCounts:
    store = TreeStore(config.output_dir, dry_run=dry_run)
    counts = WriteCounts()
    env = Environment(autoescape=False, keep_trailing_newline=True)
    metrics_tmpl = env.from_string(config.metrics_url_template) if config.metrics_url_template else None

    front_rows: list[dict[str, object]] = []

    for scan in scans:
        host = scan.server.hostname
        existing_paths = _existing_entities(config.output_dir, host)
        seen: set[tuple[str, str]] = set()
        customized: set[tuple[str, str]] = set()

        for entity in scan.entities:
            seen.add((entity.type, entity.name))
            rel = Path("servers") / host / entity.type / entity.name
            auto_res = store.write(rel / "AUTO.md", render_auto(entity))
            if auto_res.action == "created":
                counts.created += 1
            elif auto_res.action == "updated":
                counts.updated += 1
            metrics_url = _render_metrics_url(metrics_tmpl, entity)
            scaffold = render_notes(entity, metrics_url=metrics_url)
            store.write(rel / "NOTES.md", scaffold, only_if_missing=True)
            if _notes_customized(config.output_dir / rel / "NOTES.md", scaffold):
                customized.add((entity.type, entity.name))

        disappeared = [
            Entity(host=host, type=t, name=n, state="missing")
            for (t, n) in sorted(existing_paths - seen)
        ]
        if disappeared and not scan.scan_failed:
            counts.disappeared += len(disappeared)

        index_md = render_host_index(
            host,
            scan.entities,
            disappeared=disappeared,
            scan_failed=scan.scan_failed,
            customized_notes=customized,
        )
        store.write(Path("servers") / host / "INDEX.md", index_md)

        front_rows.append(
            {
                "host": host,
                "entity_count": len(scan.entities),
                "last_scan": scan.last_scan if not scan.scan_failed else f"{scan.last_scan} (FAILED)",
            }
        )

    unpushed = 0
    if config.git.enabled and not dry_run:
        repo = _repo(config)
        repo.ensure_init()
        unpushed = repo.status().commits_ahead

    store.write(Path("README.md"), render_front_page(front_rows, unpushed_commits=unpushed))
    return counts


def _notes_customized(path: Path, scaffold: str) -> bool:
    """True if NOTES.md exists and differs from the freshly-rendered scaffold.

    Dry-run note: in dry-run mode the file may not exist yet; treat that as
    "not customized" so the tick column reflects on-disk state, not intent.
    """
    if not path.exists():
        return False
    return path.read_text(encoding="utf-8") != scaffold


def _render_metrics_url(template: object, entity: Entity) -> str | None:
    if template is None:
        return None
    return template.render(host=entity.host, type=entity.type, name=entity.name)  # type: ignore[attr-defined]


def _existing_entities(output_dir: Path, host: str) -> set[tuple[str, str]]:
    """Return {(type, name)} for every entity folder under servers/<host>/."""
    root = output_dir / "servers" / host
    if not root.is_dir():
        return set()
    out: set[tuple[str, str]] = set()
    for type_dir in root.iterdir():
        if not type_dir.is_dir() or type_dir.name == "INDEX.md":
            continue
        for entity_dir in type_dir.iterdir():
            if entity_dir.is_dir():
                out.add((type_dir.name, entity_dir.name))
    return out


# ---------------------------------------------------------------- commit


def _repo(config: Config) -> GitRepo:
    return GitRepo(
        config.output_dir,
        author_name=config.git.author_name,
        author_email=config.git.author_email,
        remote=config.git.remote,
    )


def _commit_if_changed(config: Config, counts: WriteCounts, *, dry_run: bool) -> None:
    if dry_run or not config.git.enabled:
        return
    repo = _repo(config)
    repo.ensure_init()
    msg = f"scan: {_now()} +{counts.created} ~{counts.updated} -{counts.disappeared}"
    if repo.commit_all(msg):
        log.info("committed: %s", msg)
        ahead = repo.status().commits_ahead
        if ahead:
            log.warning("⚠ %d commit(s) not pushed — run `serverdocs push`", ahead)
    else:
        log.info("no changes to commit")
