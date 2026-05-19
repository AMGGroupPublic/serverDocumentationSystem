"""Configuration loader and schema."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

AdapterName = Literal["lxd", "docker", "auto"]


class GitConfig(BaseModel):
    enabled: bool = True
    author_name: str = "serverdocs"
    author_email: str = "serverdocs@local"
    remote: str = "origin"


class DiscoveryConfig(BaseModel):
    parallel: int = Field(default=8, ge=1, le=128)
    timeout_seconds: int = Field(default=30, ge=1)


class ServerEntry(BaseModel):
    name: str
    hostname: str
    ip: str | None = None
    user: str
    keyfile: str
    port: int = Field(default=22, ge=1, le=65535)
    adapters: list[AdapterName] = Field(default_factory=lambda: ["auto"])

    @property
    def address(self) -> str:
        return self.ip or self.hostname


class Config(BaseModel):
    output_dir: Path
    ssh_keys_dir: Path
    known_hosts: Path
    metrics_url_template: str = ""
    git: GitConfig = Field(default_factory=GitConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    servers: list[ServerEntry]


def load_config(path: Path) -> Config:
    """Load and validate a YAML config file."""
    with path.open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp)
    return Config.model_validate(raw)
