"""Git store tests — uses a real local repo in tmp_path."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from serverdocs.store.git import GitRepo

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def test_init_commit_status(tmp_path: Path) -> None:
    repo = GitRepo(tmp_path)
    repo.ensure_init()
    assert (tmp_path / ".git").is_dir()

    # No changes yet → commit returns False.
    assert repo.commit_all("initial") is False

    (tmp_path / "README.md").write_text("# hello\n")
    assert repo.commit_all("add readme") is True
    status = repo.status()
    assert status.has_changes is False
    assert status.commits_ahead == 0  # no remote configured


def test_status_detects_uncommitted(tmp_path: Path) -> None:
    repo = GitRepo(tmp_path)
    repo.ensure_init()
    (tmp_path / "f.txt").write_text("a")
    subprocess.run(["git", "-C", str(tmp_path), "add", "f.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "first"], check=True)
    (tmp_path / "f.txt").write_text("b")
    assert repo.status().has_changes is True
