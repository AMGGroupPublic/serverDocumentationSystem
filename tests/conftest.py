"""Shared test fixtures: in-memory FakeTransport."""

from __future__ import annotations

from collections.abc import Iterable

from serverdocs.transport.base import CmdResult, SSHTransport


class FakeTransport:
    """Returns pre-seeded outputs for specific shell commands.

    Match is by prefix to keep tests tolerant of long arg lists
    (e.g. `docker inspect <ids...>`).
    """

    def __init__(self, responses: Iterable[tuple[str, CmdResult]] | None = None) -> None:
        self._responses: list[tuple[str, CmdResult]] = list(responses or [])
        self.calls: list[str] = []

    def seed(self, prefix: str, *, stdout: str = "", stderr: str = "", exit_code: int = 0) -> None:
        self._responses.append((prefix, CmdResult(stdout=stdout, stderr=stderr, exit_code=exit_code)))

    async def __aenter__(self) -> "FakeTransport":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def run(self, command: str, *, timeout: float | None = None) -> CmdResult:
        self.calls.append(command)
        for prefix, result in self._responses:
            if command.startswith(prefix):
                return result
        return CmdResult(stdout="", stderr=f"no fake response for {command!r}", exit_code=127)

    async def which(self, binary: str) -> bool:
        result = await self.run(f"command -v {binary}")
        return result.ok and bool(result.stdout.strip())


_check: type[SSHTransport] = FakeTransport  # type: ignore[assignment]
