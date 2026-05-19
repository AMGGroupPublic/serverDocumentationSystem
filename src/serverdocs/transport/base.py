"""Transport protocol — adapters depend on this, not on asyncssh directly.

Lets us swap in a FakeTransport for tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class CmdResult:
    stdout: str
    stderr: str
    exit_code: int

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@runtime_checkable
class SSHTransport(Protocol):
    """Async SSH transport contract."""

    async def __aenter__(self) -> "SSHTransport": ...
    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None: ...

    async def run(self, command: str, *, timeout: float | None = None) -> CmdResult:
        """Run a shell command and capture stdout/stderr."""
        ...

    async def which(self, binary: str) -> bool:
        """True if ``binary`` is on $PATH on the remote host."""
        ...
