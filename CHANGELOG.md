# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Docker adapter now imports a container's project `README.md` into the doc
  tree. It probes the Compose project directory
  (`com.docker.compose.project.working_dir`) and the directories of any
  referenced compose files (`com.docker.compose.project.config_files`),
  reads the first `README.md` it finds over SSH (capped at 64 KiB), and
  writes it as machine-owned `README.imported.md` in the entity folder with
  a link from `AUTO.md`.
- Docker `AUTO.md` now shows an upstream **Source** link when the image
  carries an `org.opencontainers.image.source` label.

### Changed
- Project status promoted from pre-alpha to **beta**. README updated and
  `Development Status :: 4 - Beta` classifier added to `pyproject.toml`.
  The discover → render → commit pipeline is feature-complete and running
  in production; config schema and CLI surface are now stable.
- Compose services (`serverdocs`, `serverdocs-scheduler`, `serverdocs-sb`)
  now run as the host UID/GID configured in `docker/.env`
  (`SERVERDOCS_UID`/`SERVERDOCS_GID`, defaulting to `1000:1000`). Previously
  the containers ran as root, which made files in `data/output` and
  `keys/` root-owned and forced the host user to use `sudo` to push the
  output repo. One-time host migration: chown existing `data/` and `keys/`
  to your user (or use a one-shot `docker run --rm -v ... alpine chown`).
- `HOME=/data`, `USER`/`LOGNAME=serverdocs` added to the container env so
  asyncssh and git tooling work without a passwd entry for the host UID.

## [0.2.14] - 2026-05-19

### Added
- `serverdocs purge-disappeared HOST` — explicit, prompt-gated cleanup
  for entity dirs that no longer exist on a host. Performs a fresh
  scan, prints the list of (type, name) pairs that would be removed,
  and asks for confirmation before deleting. `-y`/`--yes` skips the
  prompt for scripting. After purge the host's INDEX is regenerated
  (Disappeared block empties) and committed to the doc repo.
- Refuses to run if the live scan failed — without fresh data we can't
  tell "host unreachable" from "container removed".

### Reverted
- The automatic "delete disappeared entities on every scan" behaviour
  from the briefly-shipped 0.2.14 prototype. Auto-deletion lost the
  intentional historical breadcrumbs in the INDEX's Disappeared block.
  Cleanup is now opt-in via the new command.

## [0.2.13] - 2026-05-19

### Added
- Each scan now removes host directories under `servers/` that are no
  longer present in `servers.yaml`. Previously, removing a host from
  config left an orphan tree behind that never got re-rendered (so it
  kept the stale layout forever — e.g. old YAML frontmatter survived
  past template changes). Safety guard: if config has zero servers
  the cleanup is skipped rather than nuking the whole tree.

## [0.2.12] - 2026-05-19

### Removed
- Inline `[auto-generated: true]` attribute from both INDEX and AUTO
  pages — every machine-rendered page has it, so it filtered nothing.
- Inline `[host: …]` attribute from INDEX and AUTO pages — the page
  path and H1 already carry the host name; cross-host enumeration is
  better served by opening the host's INDEX page directly.

### Changed
- AUTO.md inline attributes now limited to the four that enable
  cross-cutting SilverBullet queries you can't easily get from the
  tree: `type`, `name`, `state`, `last-seen`. INDEX.md has no
  inline attributes — its content is self-describing.

## [0.2.11] - 2026-05-19

### Changed
- Host `INDEX.md` and entity `AUTO.md` no longer start with a YAML
  frontmatter block. The page now opens with its heading. Metadata
  (host, type, name, state, last-seen, auto-generated) is emitted at
  the very bottom of the page as SilverBullet inline attributes
  (`[host: foo]` etc.), which remain queryable from SB without
  pushing the visible heading down the page.

## [0.2.10] - 2026-05-19

### Changed
- Scheduler loop moved out of the compose `command:` block into a real shell
  script (`docker/scheduler.sh`) baked into the image. Each cycle now logs an
  ISO-8601 timestamp, the invoked command, exit code, duration, and an
  absolute next-wake-up time, so silent failures (which the old
  `serverdocs run || true` swallowed) are now visible in `docker logs`.

### Added
- `serverdocs-scheduler` compose service: long-running container that scans on
  boot then every `SCAN_INTERVAL` seconds (default 3600). Reuses the same
  `serverdocs:dev` image so a single build covers both services.
- `FAILURE_BACKOFF` env var (default 60s) — after a failed scan the scheduler
  retries after this short delay instead of waiting a full `SCAN_INTERVAL`.
- INT/TERM trap so `docker stop` exits the scheduler cleanly with a log line
  instead of relying on SIGKILL after the 10s grace period.

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
