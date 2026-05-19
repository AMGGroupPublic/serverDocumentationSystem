"""Filesystem writes for the output tree.

Honours a dry-run mode that prints diffs instead of writing.
"""

from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class WriteResult:
    path: Path
    action: str  # "created" | "updated" | "unchanged" | "skipped-exists" | "dry-run"


class TreeStore:
    def __init__(self, root: Path, *, dry_run: bool = False) -> None:
        self.root = root
        self.dry_run = dry_run

    def write(self, relpath: Path, content: str, *, only_if_missing: bool = False) -> WriteResult:
        """Write ``content`` to ``root/relpath``.

        - ``only_if_missing=True`` skips when the file already exists (NOTES.md).
        - In dry-run mode, prints a unified diff and writes nothing.
        """
        path = self.root / relpath

        if only_if_missing and path.exists():
            return WriteResult(path, "skipped-exists")

        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if existing == content:
            return WriteResult(path, "unchanged")

        if self.dry_run:
            self._print_diff(path, existing, content)
            return WriteResult(path, "dry-run")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return WriteResult(path, "updated" if existing else "created")

    @staticmethod
    def _print_diff(path: Path, old: str, new: str) -> None:
        diff = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
        for line in diff:
            print(line, end="")
