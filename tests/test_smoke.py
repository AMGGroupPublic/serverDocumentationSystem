"""Smoke tests — confirm the scaffold imports cleanly."""

from __future__ import annotations

import serverdocs
from serverdocs.adapters import DockerAdapter, LXDAdapter
from serverdocs.model import Entity
from serverdocs.render.auto import render_auto
from serverdocs.render.front_page import render_front_page
from serverdocs.render.host_index import render_host_index
from serverdocs.render.notes import render_notes


def test_version() -> None:
    assert serverdocs.__version__ == "0.2.17"


def test_adapter_names() -> None:
    assert LXDAdapter.name == "lxd"
    assert DockerAdapter.name == "docker"


def _sample_entity() -> Entity:
    return Entity(
        host="dev001.example.com",
        type="docker",
        name="mymail",
        state="running",
        cpu=2,
        memory_mb=512,
        image="docker.io/library/postfix:latest",
    )


def test_render_auto_has_inline_attributes() -> None:
    """Cross-cutting query attributes sit at the bottom as SilverBullet
    inline attributes. host/auto-generated are intentionally omitted —
    the path and H1 already carry host, and 'auto-generated' filters
    nothing useful since only NOTES.md is hand-edited."""
    out = render_auto(_sample_entity())
    assert out.startswith("# mymail (")
    assert "[type: docker]" in out
    assert "[name: mymail]" in out
    assert "[state: running]" in out
    assert "[last-seen:" in out
    assert "auto-generated" not in out
    assert "[host:" not in out


def test_render_notes_transcludes_auto() -> None:
    out = render_notes(_sample_entity())
    assert "![[servers/dev001.example.com/docker/mymail/AUTO]]" in out


def test_render_notes_metrics_link() -> None:
    out = render_notes(_sample_entity(), metrics_url="https://g.example.com/d/mymail")
    assert "https://g.example.com/d/mymail" in out


def test_render_host_index_lists_entities() -> None:
    out = render_host_index("dev001.example.com", [_sample_entity()])
    assert "## Active" in out
    assert "mymail" in out


def test_render_front_page_banner() -> None:
    out = render_front_page(
        [{"host": "dev001.example.com", "entity_count": 1, "last_scan": "2026-05-19"}],
        unpushed_commits=3,
    )
    assert "3 commit(s) not pushed" in out
