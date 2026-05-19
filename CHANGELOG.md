# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.2] - 2026-05-19

### Changed
- `--config` now defaults to `/config/servers.yaml` (the in-container mount path)
  and reads from `SERVERDOCS_CONFIG` env var. Still overridable per-invocation.
  Lets `./serverdocs run` work without an explicit flag in the standard layout.

## [0.2.1] - 2026-05-19

### Added
- `store/known_hosts.py` — `ssh-keyscan` wrapper + idempotent append to known_hosts
- `serverdocs trust HOST [HOST...]` / `serverdocs trust --all` CLI command
- 12 new tests covering keyscan, idempotency, and CLI paths

## [0.2.0] - 2026-05-19

### Added
- `units.py` byte-size parser (decimal + binary suffixes)
- Real `AsyncSSHTransport` using `asyncssh` with key auth, pinned `known_hosts`, and per-command timeouts
- `LXDAdapter` parses `lxc list --format json` into `Entity` (cpu pinning ranges, memory, disks, networks excluding lo/link-local)
- `DockerAdapter` runs `docker ps` + `docker inspect`, parses `NanoCpus`/`CpusetCpus`, memory, mounts, network IPs
- Full pipeline: parallel fan-out with `asyncio.Semaphore`, per-host failure isolation, diff against existing tree (created/updated/disappeared), git commit with structured message, push-needed banner on root README
- `serverdocs push` CLI command actually pushes
- Test suite: 48 tests, 87% coverage, `FakeTransport` for adapter golden-file tests, click `CliRunner` integration

### Changed
- `validate-config` command renamed (was `validate_config`) for consistent hyphen form

## [0.1.0] - 2026-05-19

Initial scaffold.
