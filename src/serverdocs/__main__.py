"""Click CLI entry point: ``serverdocs <command>``."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click

from . import __version__
from .config import load_config
from .pipeline import run as pipeline_run
from .store.git import GitRepo
from .store.known_hosts import trust_host

log = logging.getLogger("serverdocs")


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
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Path to YAML config file.",
)
def validate_config(config_path: Path) -> None:
    """Validate the config file and exit."""
    cfg = load_config(config_path)
    click.echo(f"OK: {len(cfg.servers)} server(s) configured.")


@cli.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
def run(config_path: Path) -> None:
    """Discover, render, commit."""
    cfg = load_config(config_path)
    rc = asyncio.run(pipeline_run(cfg, dry_run=False))
    sys.exit(rc)


@cli.command("dry-run")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
def dry_run(config_path: Path) -> None:
    """Discover and render, but write nothing and skip git commit."""
    cfg = load_config(config_path)
    rc = asyncio.run(pipeline_run(cfg, dry_run=True))
    sys.exit(rc)


@cli.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
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
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
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
    if all_hosts:
        targets = [s.address for s in cfg.servers]
    elif hosts:
        targets = list(hosts)
    else:
        raise click.UsageError("Specify one or more hosts, or use --all.")

    fail = False
    for host in targets:
        res = trust_host(host, cfg.known_hosts, port=port, timeout=timeout)
        if res.ok:
            click.echo(f"{host}: added {res.added}, skipped {res.skipped}")
        else:
            click.echo(f"{host}: FAILED — {res.error}", err=True)
            fail = True
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    cli()
