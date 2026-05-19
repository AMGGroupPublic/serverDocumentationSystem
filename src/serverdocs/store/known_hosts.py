"""Bootstrap and maintain the pinned ``known_hosts`` file via ``ssh-keyscan``."""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


class KeyscanError(RuntimeError):
    """Raised when ssh-keyscan cannot run at all (binary missing, etc.)."""


@dataclass
class TrustResult:
    host: str
    added: int = 0
    skipped: int = 0
    error: str | None = None
    keys: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None


def fetch_host_keys(host: str, *, port: int = 22, timeout: int = 10) -> list[str]:
    """Run ``ssh-keyscan`` and return the public-key lines for ``host``.

    Returns an empty list if ssh-keyscan ran but produced no usable keys
    (e.g. host unreachable). Raises ``KeyscanError`` if the binary is missing.
    """
    if shutil.which("ssh-keyscan") is None:
        raise KeyscanError("ssh-keyscan not found on PATH")
    proc = subprocess.run(
        ["ssh-keyscan", "-T", str(timeout), "-p", str(port), host],
        capture_output=True,
        text=True,
        check=False,
    )
    keys = [
        line
        for line in proc.stdout.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not keys and proc.stderr:
        log.debug("ssh-keyscan(%s) stderr: %s", host, proc.stderr.strip())
    return keys


def update_known_hosts(path: Path, new_lines: list[str]) -> tuple[int, int]:
    """Append unique entries from ``new_lines`` to ``path``.

    Returns ``(added, skipped)``. Idempotent: re-running with the same lines is a no-op.
    """
    existing: set[str] = set()
    if path.exists():
        existing = {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()}

    to_write: list[str] = []
    added = 0
    skipped = 0
    for line in new_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in existing:
            skipped += 1
            continue
        existing.add(stripped)
        to_write.append(stripped)
        added += 1

    if to_write:
        path.parent.mkdir(parents=True, exist_ok=True)
        prefix = ""
        if path.exists() and path.stat().st_size > 0:
            tail = path.read_text(encoding="utf-8")[-1:]
            if tail and tail != "\n":
                prefix = "\n"
        with path.open("a", encoding="utf-8") as fp:
            fp.write(prefix + "\n".join(to_write) + "\n")

    return added, skipped


def trust_host(host: str, known_hosts: Path, *, port: int = 22, timeout: int = 10) -> TrustResult:
    """Fetch host keys and add them to ``known_hosts``."""
    result = TrustResult(host=host)
    try:
        keys = fetch_host_keys(host, port=port, timeout=timeout)
    except KeyscanError as exc:
        result.error = str(exc)
        return result
    if not keys:
        result.error = "no keys returned (host unreachable or no SSH)"
        return result
    result.keys = keys
    result.added, result.skipped = update_known_hosts(known_hosts, keys)
    return result
