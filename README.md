# serverdocs

Discover VMs and containers across a fleet of servers via SSH, and maintain a
plain-markdown wiki tree that's editable through [SilverBullet](https://silverbullet.md/).

## Status

**Beta.** The discovery → render → commit pipeline is feature-complete and
running in production against AMG's internal fleet. Behaviour and config
schema are stable, but expect occasional rough edges around new adapters,
edge-case host topologies, and CLI ergonomics. See `IDEA.md` for the
original concept.

## What it does (v1)

- SSH to a list of physical servers defined in YAML config
- Probe each host for supported adapters (**LXD**, **Docker** in v1)
- Build a normalised `Entity` per VM/container with static specs
  (CPU, RAM, disks, image, networks, state)
- Render a markdown tree:
  - `servers/<host>/<type>/<name>/AUTO.md` — machine-owned, regenerated each run
  - `servers/<host>/<type>/<name>/NOTES.md` — human-owned, scaffold once, transcludes AUTO via `![[...]]`
  - `servers/<host>/INDEX.md` — per-host index
  - `README.md` — root front page with "push needed" banner
- Commit the tree to a local git repo on every run
- `serverdocs push` (CLI) or `/push-docs` (SilverBullet slash command) to push manually

## Quick start

```bash
# install (dev mode)
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# configure
cp config/servers.example.yaml config/servers.yaml
# edit servers.yaml

# pin the host keys you'll be connecting to
serverdocs trust --config config/servers.yaml --all

# run
serverdocs run --config config/servers.yaml
```

### Running via the container

The containers run as your host user, so files written into `data/` and
`keys/` keep host ownership and you can `git push` from `data/output` without
sudo. Set your UID/GID in `docker/.env`:

```bash
cp docker/.env.example docker/.env
# edit if `id -u` / `id -g` aren't 1000
```

The repo ships a `./serverdocs` wrapper that proxies into the compose service —
all args are passed through, paths inside the container are the ones from the
volume mounts (`/config`, `/keys`, `/data`).

```bash
./serverdocs --help
./serverdocs trust --all
./serverdocs run
```

`--config` defaults to `/config/servers.yaml` (the in-container mount of
`./config/servers.yaml`), so you only need the flag when pointing at a
non-default file. Override with `--config <path>` or `SERVERDOCS_CONFIG=<path>`.

The wrapper auto-detects `docker compose` (v2) vs `docker-compose` (legacy)
and disables TTY allocation when piping output.

### Scheduled scans

A long-running `serverdocs-scheduler` service is included in the compose stack.
It runs an initial scan on boot, then re-scans every `SCAN_INTERVAL` seconds
(default `3600` = hourly). Start it with:

```bash
cd docker && docker compose up -d serverdocs-scheduler serverdocs-sb
```

Override the interval inline or in a `.env` file:

```bash
SCAN_INTERVAL=900 docker compose up -d serverdocs-scheduler
```

If a scan fails the scheduler retries after `FAILURE_BACKOFF` seconds
(default `60`) instead of waiting a full interval — also overridable via env.

The scheduler logs every cycle with an ISO-8601 UTC timestamp, the invoked
command, exit code, duration and the absolute next-wake time, so `docker logs
serverdocs-scheduler` shows exactly when scans ran and whether they succeeded.

The one-shot `serverdocs` service still exists for manual scans via the
`./serverdocs` wrapper — both share the same image.

## Commands

All commands accept `--config <path>` (defaults to `/config/servers.yaml`;
also honours the `SERVERDOCS_CONFIG` env var).

| Command | Purpose |
|---|---|
| `serverdocs validate-config` | Lint the YAML config and exit |
| `serverdocs trust HOST [HOST...]` | Run ssh-keyscan and pin keys into the configured known_hosts |
| `serverdocs trust --all` | Same, for every server in the config |
| `serverdocs dry-run` | Scan and print diffs, write nothing, no git commit |
| `serverdocs run` | Full scan: discover, render, commit locally |
| `serverdocs push` | Push the local doc repo to its configured remote |
| `serverdocs purge-disappeared HOST` | Scan HOST, list entity dirs that no longer exist on it, prompt for confirmation, then delete (`-y` to skip the prompt) |

## Configuration

See [`config/servers.example.yaml`](config/servers.example.yaml).

## Layout

```
src/serverdocs/
├── __main__.py          # Click CLI
├── config.py            # YAML loader + pydantic schema
├── model.py             # Entity dataclass
├── transport/           # SSH transport
├── adapters/            # Per-runtime discovery (lxd, docker)
├── render/              # Entity → markdown
├── store/               # Filesystem + git operations
└── pipeline.py          # Orchestration
```

## Roadmap

- HyperV / XEN adapters
- Live-metrics integration (currently just a templated link)
- Recursive discovery (physical host → VM → docker-in-VM)

## License

MIT — see [LICENSE](LICENSE).
