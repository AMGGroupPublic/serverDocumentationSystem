"""Click CLI entry point: ``serverdocs <command>``."""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import click

from . import __version__
from .config import load_config
from .pipeline import (
    disappeared_for,
    purge_entities,
    rerender_host_index,
    run as pipeline_run,
    scan_host,
)
from .store.git import GitRepo
from .store.known_hosts import trust_host

log = logging.getLogger("serverdocs")

DEFAULT_CONFIG_PATH = "/config/servers.yaml"

F = TypeVar("F", bound=Callable[..., object])


def config_option(f: F) -> F:
    """``--config`` option shared by every subcommand.

    Defaults to the in-container path so the host-side ``./serverdocs`` wrapper
    works without an explicit flag. Overridable via flag or ``SERVERDOCS_CONFIG``.
    """
    return click.option(  # type: ignore[return-value]
        "--config",
        "config_path",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
        default=DEFAULT_CONFIG_PATH,
        show_default=True,
        envvar="SERVERDOCS_CONFIG",
        help="Path to YAML config file. Env: SERVERDOCS_CONFIG.",
    )(f)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )


@click.group()
@click.version_option(__version__, prog_name="serverdocs")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool) -> None:
    """serverdocs — discover and document VMs/containers across servers."""
    _setup_logging(verbose)


@cli.command("validate-config")
@config_option
def validate_config(config_path: Path) -> None:
    """Validate the config file and exit."""
    cfg = load_config(config_path)
    click.echo(f"OK: {len(cfg.servers)} server(s) configured.")


@cli.command()
@config_option
def run(config_path: Path) -> None:
    """Discover, render, commit."""
    cfg = load_config(config_path)
    rc = asyncio.run(pipeline_run(cfg, dry_run=False))
    sys.exit(rc)


@cli.command("dry-run")
@config_option
def dry_run(config_path: Path) -> None:
    """Discover and render, but write nothing and skip git commit."""
    cfg = load_config(config_path)
    rc = asyncio.run(pipeline_run(cfg, dry_run=True))
    sys.exit(rc)


@cli.command()
@config_option
def push(config_path: Path) -> None:
    """Push the local doc repo to its configured remote."""
    cfg = load_config(config_path)
    repo = GitRepo(
        cfg.output_dir,
        author_name=cfg.git.author_name,
        author_email=cfg.git.author_email,
        remote=cfg.git.remote,
    )
    repo.push()
    click.echo(f"Pushed {cfg.output_dir} → {cfg.git.remote}")


@cli.command()
@config_option
@click.option("--all", "all_hosts", is_flag=True, help="Trust every server in the config.")
@click.option("--port", default=22, show_default=True, help="SSH port.")
@click.option("--timeout", default=10, show_default=True, help="ssh-keyscan timeout (seconds).")
@click.argument("hosts", nargs=-1)
def trust(
    config_path: Path,
    all_hosts: bool,
    port: int,
    timeout: int,
    hosts: tuple[str, ...],
) -> None:
    """Run ssh-keyscan against HOSTS (or --all) and pin keys into known_hosts."""
    cfg = load_config(config_path)
    if all_hosts and hosts:
        raise click.UsageError("Pass either --all or explicit hosts, not both.")
    targets: list[tuple[str, int]]
    if all_hosts:
        # Honour each server's configured port when iterating from config.
        targets = [(s.address, s.port) for s in cfg.servers]
    elif hosts:
        targets = [(h, port) for h in hosts]
    else:
        raise click.UsageError("Specify one or more hosts, or use --all.")

    fail = False
    for host, host_port in targets:
        res = trust_host(host, cfg.known_hosts, port=host_port, timeout=timeout)
        label = host if host_port == 22 else f"{host}:{host_port}"
        if res.ok:
            click.echo(f"{label}: added {res.added}, skipped {res.skipped}")
        else:
            click.echo(f"{label}: FAILED — {res.error}", err=True)
            fail = True
    if fail:
        sys.exit(1)


@cli.command("purge-disappeared")
@config_option
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt.")
@click.argument("host")
def purge_disappeared(config_path: Path, yes: bool, host: str) -> None:
    """Delete entity dirs under HOST that are no longer present on the live host.

    Performs a fresh scan of HOST, lists what would be deleted, and prompts
    for confirmation before removing anything. HOST may be a hostname or the
    short ``name`` from the config file.
    """
    cfg = load_config(config_path)
    try:
        server, scan = asyncio.run(scan_host(cfg, host))
    except ValueError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)

    if scan.scan_failed:
        click.echo(
            f"{server.hostname}: scan failed — {scan.error}\n"
            "refusing to purge while the host is unreachable.",
            err=True,
        )
        sys.exit(2)

    disappeared = disappeared_for(cfg, server.hostname, scan)
    if not disappeared:
        click.echo(f"{server.hostname}: no disappeared entities to purge.")
        return

    noun = "entity" if len(disappeared) == 1 else "entities"
    click.echo(f"{server.hostname}: {len(disappeared)} disappeared {noun}:")
    for t, n in disappeared:
        click.echo(f"  - {t}/{n}")

    if not yes:
        click.confirm(
            f"\nDelete {len(disappeared)} director{'y' if len(disappeared) == 1 else 'ies'} under "
            f"{cfg.output_dir / 'servers' / server.hostname}?",
            abort=True,
        )

    removed = purge_entities(cfg, server.hostname, disappeared)
    rerender_host_index(cfg, server.hostname, scan, removed=removed)
    click.echo(f"removed {removed} {'entity' if removed == 1 else 'entities'} from {server.hostname}.")


if __name__ == "__main__":
    cli()
