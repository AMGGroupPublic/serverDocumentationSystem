"""Docker adapter tests."""

from __future__ import annotations

import json

import pytest

from serverdocs.adapters.docker import DockerAdapter

from .conftest import FakeTransport

_PS_OUT = (
    json.dumps({"ID": "abc123def456", "Names": "mymail", "Image": "postfix:latest"}) + "\n"
    + json.dumps({"ID": "999fff888eee", "Names": "nginx", "Image": "nginx:alpine"}) + "\n"
)

_INSPECT_OUT = json.dumps(
    [
        {
            "Id": "abc123def456",
            "Name": "/mymail",
            "Created": "2024-01-15T10:30:00Z",
            "State": {"Status": "running"},
            "Config": {
                "Image": "postfix:latest",
                "ExposedPorts": {"25/tcp": {}, "587/tcp": {}},
            },
            "HostConfig": {
                "Memory": 536_870_912,        # 512 MiB → ~537 MB
                "NanoCpus": 2_000_000_000,    # 2 CPUs
                "RestartPolicy": {"Name": "unless-stopped"},
            },
            "Mounts": [
                {"Type": "volume", "Name": "mail-data", "Source": "/var/lib/docker/volumes/mail-data/_data", "Destination": "/var/mail"},
                {"Type": "bind", "Source": "/etc/postfix", "Destination": "/etc/postfix"},
            ],
            "NetworkSettings": {
                "Networks": {
                    "bridge": {
                        "IPAddress": "172.17.0.2",
                        "GlobalIPv6Address": "",
                        "MacAddress": "02:42:ac:11:00:02",
                    }
                }
            },
        },
        {
            "Id": "999fff888eee",
            "Name": "/nginx",
            "Created": "2024-02-01T00:00:00Z",
            "State": {"Status": "exited"},
            "Config": {"Image": "nginx:alpine"},
            "HostConfig": {"Memory": 0, "NanoCpus": 0, "CpusetCpus": "0-3"},
            "Mounts": [],
            "NetworkSettings": {"Networks": {}},
        },
    ]
)


@pytest.mark.asyncio
async def test_docker_parses_running_container() -> None:
    transport = FakeTransport()
    transport.seed("docker ps", stdout=_PS_OUT)
    transport.seed("docker inspect", stdout=_INSPECT_OUT)
    adapter = DockerAdapter("dev001.example.com")

    entities = await adapter.discover(transport)
    assert len(entities) == 2
    mail = next(e for e in entities if e.name == "mymail")
    assert mail.state == "running"
    assert mail.cpu == 2
    assert mail.memory_mb == 537
    assert mail.image == "postfix:latest"
    assert mail.created_at == "2024-01-15T10:30:00Z"
    assert mail.extra["restart_policy"] == "unless-stopped"
    assert {"25/tcp", "587/tcp"} == set(mail.extra["ports"])

    mounts = {d.mount for d in mail.disks}
    assert mounts == {"/var/mail", "/etc/postfix"}

    net = next(n for n in mail.networks if n.iface == "bridge")
    assert net.ipv4 == "172.17.0.2"
    assert net.mac == "02:42:ac:11:00:02"


@pytest.mark.asyncio
async def test_docker_cpuset_fallback() -> None:
    transport = FakeTransport()
    transport.seed("docker ps", stdout=_PS_OUT)
    transport.seed("docker inspect", stdout=_INSPECT_OUT)
    adapter = DockerAdapter("h")
    entities = await adapter.discover(transport)
    nginx = next(e for e in entities if e.name == "nginx")
    assert nginx.cpu == 4  # CpusetCpus 0-3
    assert nginx.memory_mb is None
    assert nginx.state == "exited"


@pytest.mark.asyncio
async def test_docker_empty_when_no_containers() -> None:
    transport = FakeTransport()
    transport.seed("docker ps", stdout="")
    adapter = DockerAdapter("h")
    assert await adapter.discover(transport) == []


@pytest.mark.asyncio
async def test_docker_ps_failure_returns_empty() -> None:
    transport = FakeTransport()
    transport.seed("docker ps", stderr="permission denied", exit_code=1)
    adapter = DockerAdapter("h")
    assert await adapter.discover(transport) == []


_PS_COMPOSE = json.dumps({"ID": "c0ffee123456", "Names": "web", "Image": "ghcr.io/acme/web"}) + "\n"

_INSPECT_COMPOSE = json.dumps(
    [
        {
            "Id": "c0ffee123456",
            "Name": "/web",
            "Created": "2024-03-01T00:00:00Z",
            "State": {"Status": "running"},
            "Config": {
                "Image": "ghcr.io/acme/web",
                "Labels": {
                    "com.docker.compose.project.working_dir": "/srv/acme/web",
                    "com.docker.compose.project.config_files": "/srv/acme/web/docker-compose.yml",
                    "org.opencontainers.image.source": "https://github.com/acme/web",
                },
            },
            "HostConfig": {},
            "Mounts": [],
            "NetworkSettings": {"Networks": {}},
        }
    ]
)


@pytest.mark.asyncio
async def test_docker_extracts_source_url_and_imports_readme() -> None:
    transport = FakeTransport()
    transport.seed("docker ps", stdout=_PS_COMPOSE)
    transport.seed("docker inspect", stdout=_INSPECT_COMPOSE)
    transport.seed("head -c 65536 -- /srv/acme/web/README.md", stdout="# web\n\nProject docs.\n")
    adapter = DockerAdapter("dev001.example.com")

    entities = await adapter.discover(transport)
    web = entities[0]

    assert web.source_url == "https://github.com/acme/web"
    assert web.readme is not None
    assert web.readme.source_path == "/srv/acme/web/README.md"
    assert "Project docs." in web.readme.content


@pytest.mark.asyncio
async def test_docker_falls_back_to_config_file_dir_for_readme() -> None:
    """No working_dir label, but a compose config file path is present."""
    inspect = json.dumps(
        [
            {
                "Id": "c0ffee123456",
                "Name": "/web",
                "State": {"Status": "running"},
                "Config": {
                    "Image": "x",
                    "Labels": {
                        "com.docker.compose.project.config_files": "/opt/stack/compose.yaml",
                    },
                },
                "HostConfig": {},
                "Mounts": [],
                "NetworkSettings": {"Networks": {}},
            }
        ]
    )
    transport = FakeTransport()
    transport.seed("docker ps", stdout=_PS_COMPOSE)
    transport.seed("docker inspect", stdout=inspect)
    transport.seed("head -c 65536 -- /opt/stack/README.md", stdout="readme body")
    adapter = DockerAdapter("h")

    web = (await adapter.discover(transport))[0]
    assert web.readme is not None
    assert web.readme.source_path == "/opt/stack/README.md"


@pytest.mark.asyncio
async def test_docker_no_readme_when_no_compose_labels() -> None:
    transport = FakeTransport()
    transport.seed("docker ps", stdout=_PS_OUT)
    transport.seed("docker inspect", stdout=_INSPECT_OUT)
    adapter = DockerAdapter("h")

    entities = await adapter.discover(transport)
    assert all(e.readme is None for e in entities)
    assert all(e.source_url is None for e in entities)


@pytest.mark.asyncio
async def test_docker_missing_readme_file_leaves_readme_none() -> None:
    transport = FakeTransport()
    transport.seed("docker ps", stdout=_PS_COMPOSE)
    transport.seed("docker inspect", stdout=_INSPECT_COMPOSE)
    # head returns nonzero when the file is absent — default FakeTransport miss
    # yields exit_code 127, so no seed for the head command is needed.
    adapter = DockerAdapter("dev001.example.com")

    web = (await adapter.discover(transport))[0]
    assert web.readme is None
    assert web.source_url == "https://github.com/acme/web"
