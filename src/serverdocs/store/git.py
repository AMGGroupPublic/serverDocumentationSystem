"""Thin wrapper around the system git binary.

Shells out rather than importing gitpython — fewer deps, same surface.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


class GitCommandError(RuntimeError):
    """Raised when a git invocation exits non-zero; carries stderr in the message."""


@dataclass
class GitStatus:
    has_changes: bool
    commits_ahead: int


class GitRepo:
    def __init__(
        self,
        root: Path,
        *,
        author_name: str = "serverdocs",
        author_email: str = "serverdocs@local",
        remote: str = "origin",
    ) -> None:
        self.root = root
        self.author_name = author_name
        self.author_email = author_email
        self.remote = remote

    # ---- low-level ----------------------------------------------------

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        # -c safe.directory=<root>: when /data is bind-mounted into the
        # container, files on disk are owned by the host UID but git runs as
        # root inside. Git 2.35+ refuses to operate on "dubious ownership"
        # repos; this opt-in tells it to trust this specific path.
        cmd = ["git", "-c", f"safe.directory={self.root}", *args]
        try:
            return subprocess.run(
                cmd, cwd=self.root, check=check, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip() or "(no stderr)"
            raise GitCommandError(
                f"git command failed (exit {exc.returncode}):\n"
                f"  cmd: {' '.join(cmd)}\n"
                f"  cwd: {self.root}\n"
                f"  stderr: {stderr}"
            ) from exc

    # ---- public api ---------------------------------------------------

    def ensure_init(self) -> None:
        if not (self.root / ".git").exists():
            self.root.mkdir(parents=True, exist_ok=True)
            self._run("init", "-q")
            self._run("config", "user.name", self.author_name)
            self._run("config", "user.email", self.author_email)

    def status(self) -> GitStatus:
        porcelain = self._run("status", "--porcelain").stdout
        has_changes = bool(porcelain.strip())
        ahead = 0
        try:
            out = self._run(
                "rev-list", "--count", f"{self.remote}/HEAD..HEAD", check=False
            )
            if out.returncode == 0:
                ahead = int(out.stdout.strip() or "0")
        except (ValueError, subprocess.SubprocessError):
            ahead = 0
        return GitStatus(has_changes=has_changes, commits_ahead=ahead)

    def commit_all(self, message: str) -> bool:
        """Stage everything and commit. Returns True if a commit was made."""
        self._clear_stale_index_lock()
        self._run("add", "-A")
        if not self._run("status", "--porcelain").stdout.strip():
            return False
        self._run("commit", "-q", "-m", message)
        return True

    def _clear_stale_index_lock(self, max_age_seconds: int = 60) -> None:
        """Remove `.git/index.lock` if it's older than ``max_age_seconds``.

        A live git operation completes in milliseconds; anything that age
        is almost certainly a leftover from a crashed earlier run. The age
        gate avoids clobbering a concurrent legitimate git process.
        """
        lock = self.root / ".git" / "index.lock"
        if not lock.exists():
            return
        age = time.time() - lock.stat().st_mtime
        if age <= max_age_seconds:
            return
        log.warning(
            "Removing stale .git/index.lock (age %.0fs) — likely left by a crashed run",
            age,
        )
        try:
            lock.unlink()
        except OSError as exc:
            log.warning("Failed to remove stale lock %s: %s", lock, exc)

    def push(self) -> None:
        self._run("push", self.remote)
