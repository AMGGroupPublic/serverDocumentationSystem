"""Render an Entity's NOTES.md scaffold.

This file is human-owned. Discovery only creates it when missing;
subsequent runs never modify it.
"""

from __future__ import annotations

from jinja2 import Environment

from ..model import Entity

_TEMPLATE = """\
---
host: {{ entity.host }}
type: {{ entity.type }}
name: {{ entity.name }}
---

# {{ entity.name }}

## Purpose
_(describe what this {{ entity.type }} does)_

## Owner
_(team / person responsible)_

## Auto-discovered details

![[servers/{{ entity.host }}/{{ entity.type }}/{{ entity.name }}/AUTO]]
{% if metrics_url %}
## Live metrics

[Open dashboard]({{ metrics_url }})
{% endif %}
"""


def render_notes(entity: Entity, *, metrics_url: str | None = None) -> str:
    env = Environment(autoescape=False, keep_trailing_newline=True)
    return env.from_string(_TEMPLATE).render(entity=entity, metrics_url=metrics_url)
