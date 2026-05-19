# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `serverdocs-scheduler` compose service: long-running container that scans on
  boot then every `SCAN_INTERVAL` seconds (default 3600). Reuses the same
  `serverdocs:dev` image so a single build covers both services.

## [0.2.9] - 2026-05-19

### Fixed
- Crashed scans were leaving `.git/index.lock` behind, blocking every
  subsequent run with `Unable to create '.git/index.lock': File exists`.
  `GitRepo.commit_all` now sweeps stale locks older than 60s before staging
  (preserves fresh locks in case a legitimate concurrent git op is running).

### Added
- Process-wide `flock` mutex around `pipeline.run`. Concurrent `./serverdocs run`
  + scheduler ticks no longer race on the output tree; the second invocation
  waits up to 5s, then logs a warning and skips cleanly (exit 0). Dry-run is
  exempt — it writes nothing and shouldn't block live scans.

## [0.2.8] - 2026-05-19

### Fixed
- `git add -A` failing with exit 128 inside the container due to git's
  "dubious ownership" check on bind-mounted volumes (host UID ≠ container UID).
  All git invocations now pass `-c safe.directory=<root>` to opt out for the
  specific repo path. No host-side or chown workarounds required.

### Changed
- Subprocess errors from the git layer now raise `GitCommandError` with cmd,
  cwd and stderr embedded in the message — previous `CalledProcessError` only
  showed the exit code, hiding the real failure reason in logs.

## [0.2.7] - 2026-05-19

### Added
- Explicit "← Back" links at the bottom of `AUTO.md` (transcluded into NOTES)
  and host `INDEX.md`. Both use the `#heading` anchor form, so SilverBullet
  navigates to the heading on click rather than restoring the previous cursor
  position — which fixed the bug where returning to the index dropped the
  cursor inside a table row and flipped that row into edit mode.
- Back-link lives in AUTO.md (regenerated every run) rather than NOTES.md so
  the per-entity "edited?" check on the host index stays stable across upgrades.

## [0.2.6] - 2026-05-19

### Changed
- Internal navigation links in generated markdown now use SilverBullet wikilink
  form `[[path|alias]]` instead of `[alias](path.md)`. SB opens wikilinks in the
  current tab; the previous markdown form spawned a new tab on every click.
  External URLs (GitHub etc.) are untouched.

## [0.2.5] - 2026-05-19

### Added
- Host `INDEX.md` gains a "Notes" column between State and CPU. ✅ when the
  entity's `NOTES.md` has been edited away from the auto-generated scaffold,
  ❌ otherwise. Computed during scan by diffing the on-disk file against the
  freshly-rendered scaffold (deterministic for stable config).

## [0.2.4] - 2026-05-19

### Changed
- Host `INDEX.md` now lists running entities first (alphabetical, case-insensitive),
  then everything else (alphabetical, case-insensitive). Previously order matched
  whatever the adapter returned.

## [0.2.3] - 2026-05-19

### Added
- `port` field on each server entry in the config (defaults to 22, validated 1-65535)
- `pipeline._scan_server` and `serverdocs trust --all` honour the per-server port
- `trust` output shows `host:port` only when port is non-default

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
