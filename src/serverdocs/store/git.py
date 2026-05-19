"""Thin wrapper around the system git binary.

Shells out rather than importing gitpython — fewer deps, same surface.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


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
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=check,
            capture_output=True,
            text=True,
        )

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
        self._run("add", "-A")
        if not self._run("status", "--porcelain").stdout.strip():
            return False
        self._run("commit", "-q", "-m", message)
        return True

    def push(self) -> None:
        self._run("push", self.remote)
