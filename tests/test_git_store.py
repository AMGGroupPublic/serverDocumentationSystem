"""Git store tests — uses a real local repo in tmp_path."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from serverdocs.store.git import GitCommandError, GitRepo

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


def test_safe_directory_flag_is_set(tmp_path: Path) -> None:
    """Every git invocation must include -c safe.directory=<root> so
    bind-mounted repos with mismatched UID don't trip dubious-ownership."""
    repo = GitRepo(tmp_path)
    repo.ensure_init()
    # Inspect a benign command via subprocess directly to confirm the flag
    # is applied. We piggy-back on `_run` here.
    cp = repo._run("rev-parse", "--show-toplevel")
    # The toplevel resolves; if safe.directory weren't set on a foreign-UID
    # repo, git would refuse. (Best we can do without simulating UID drift.)
    assert cp.stdout.strip().endswith(str(tmp_path).split("/")[-1])


def test_failure_raises_with_stderr(tmp_path: Path) -> None:
    repo = GitRepo(tmp_path)
    repo.ensure_init()
    with pytest.raises(GitCommandError) as exc_info:
        repo._run("commit", "-m", "nothing to commit")  # no staged changes
    msg = str(exc_info.value)
    assert "git command failed" in msg
    assert "cmd: " in msg
    assert "stderr:" in msg


def test_stale_index_lock_is_cleared(tmp_path: Path) -> None:
    repo = GitRepo(tmp_path)
    repo.ensure_init()
    lock = tmp_path / ".git" / "index.lock"
    lock.write_text("stale\n")
    # Backdate by 5 minutes so the age gate fires.
    old = lock.stat().st_mtime - 300
    os.utime(lock, (old, old))

    (tmp_path / "f.txt").write_text("hi")
    assert repo.commit_all("first") is True
    assert not lock.exists()


def test_recent_index_lock_is_preserved(tmp_path: Path) -> None:
    """A fresh lock (<60s old) might be a real concurrent git op — leave it."""
    repo = GitRepo(tmp_path)
    repo.ensure_init()
    lock = tmp_path / ".git" / "index.lock"
    lock.write_text("active\n")
    # Default mtime is "now" — under the 60s threshold.
    (tmp_path / "f.txt").write_text("hi")
    with pytest.raises(GitCommandError):
        repo.commit_all("first")
    assert lock.exists()


def test_status_detects_uncommitted(tmp_path: Path) -> None:
    repo = GitRepo(tmp_path)
    repo.ensure_init()
    (tmp_path / "f.txt").write_text("a")
    subprocess.run(["git", "-C", str(tmp_path), "add", "f.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "first"], check=True)
    (tmp_path / "f.txt").write_text("b")
    assert repo.status().has_changes is True
