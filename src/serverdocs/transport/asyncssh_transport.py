"""asyncssh-backed implementation of SSHTransport."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import asyncssh

from .base import CmdResult, SSHTransport

if TYPE_CHECKING:
    from types import TracebackType

log = logging.getLogger(__name__)


class TransportError(RuntimeError):
    """Raised when the SSH connection cannot be established."""


class AsyncSSHTransport:
    """Single-host SSH transport."""

    def __init__(
        self,
        *,
        host: str,
        user: str,
        keyfile: Path,
        known_hosts: Path,
        timeout: float = 30.0,
        port: int = 22,
    ) -> None:
        self.host = host
        self.user = user
        self.keyfile = keyfile
        self.known_hosts = known_hosts
        self.timeout = timeout
        self.port = port
        self._conn: asyncssh.SSHClientConnection | None = None

    async def __aenter__(self) -> "AsyncSSHTransport":
        if not self.keyfile.exists():
            raise TransportError(f"SSH keyfile missing: {self.keyfile}")
        if not self.known_hosts.exists():
            raise TransportError(
                f"known_hosts missing: {self.known_hosts} — add the host's key first"
            )
        log.debug("connecting to %s@%s:%d", self.user, self.host, self.port)
        try:
            self._conn = await asyncio.wait_for(
                asyncssh.connect(
                    self.host,
                    port=self.port,
                    username=self.user,
                    client_keys=[str(self.keyfile)],
                    known_hosts=str(self.known_hosts),
                ),
                timeout=self.timeout,
            )
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise TransportError(f"connect timeout to {self.host}") from exc
        except (OSError, asyncssh.Error) as exc:
            raise TransportError(f"connect failed to {self.host}: {exc}") from exc
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: "TracebackType | None",
    ) -> None:
        if self._conn is not None:
            self._conn.close()
            await self._conn.wait_closed()
            self._conn = None

    async def run(self, command: str, *, timeout: float | None = None) -> CmdResult:
        if self._conn is None:
            raise TransportError("transport not opened — use `async with`")
        eff_timeout = timeout if timeout is not None else self.timeout
        try:
            result: Any = await asyncio.wait_for(
                self._conn.run(command, check=False), timeout=eff_timeout
            )
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise TransportError(f"command timed out on {self.host}: {command!r}") from exc
        return CmdResult(
            stdout=_to_str(result.stdout),
            stderr=_to_str(result.stderr),
            exit_code=result.exit_status if result.exit_status is not None else -1,
        )

    async def which(self, binary: str) -> bool:
        result = await self.run(f"command -v {binary}")
        return result.ok and bool(result.stdout.strip())


def _to_str(buf: object) -> str:
    if buf is None:
        return ""
    if isinstance(buf, bytes):
        return buf.decode("utf-8", errors="replace")
    return str(buf)


# Static check: this class satisfies the protocol.
_: type[SSHTransport] = AsyncSSHTransport  # type: ignore[assignment]
