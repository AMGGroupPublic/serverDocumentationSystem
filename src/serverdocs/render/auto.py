"""Render an Entity to AUTO.md.

This file is machine-owned and overwritten on every run.
Output is deterministic so git diffs are clean.
"""

from __future__ import annotations

from jinja2 import Environment

from ..model import Entity

_TEMPLATE = """\
# {{ entity.name }} ({{ entity.type }} on {{ entity.host }})

| Field | Value |
|---|---|
| State | {{ entity.state }} |
| CPU | {{ entity.cpu if entity.cpu is not none else "?" }} |
| Memory (MB) | {{ entity.memory_mb if entity.memory_mb is not none else "?" }} |
| Image | {{ entity.image or "?" }} |
| Created | {{ entity.created_at or "?" }} |
| Last seen | {{ entity.last_seen }} |
{% if entity.source_url %}| Source | [{{ entity.source_url }}]({{ entity.source_url }}) |
{% endif %}
{% if entity.readme %}
## Project README

Imported from `{{ entity.readme.source_path }}` on {{ entity.host }}.

[[servers/{{ entity.host }}/{{ entity.type }}/{{ entity.name }}/README.imported|Open README]]
{% endif %}
{% if entity.disks %}
## Disks

| Name | Size (MB) | Mount |
|---|---|---|
{% for d in entity.disks -%}
| {{ d.name }} | {{ d.size_mb if d.size_mb is not none else "?" }} | {{ d.mount or "" }} |
{% endfor %}
{% endif %}
{% if entity.networks %}
## Networks

| Interface | IPv4 | IPv6 | MAC |
|---|---|---|---|
{% for n in entity.networks -%}
| {{ n.iface }} | {{ n.ipv4 or "" }} | {{ n.ipv6 or "" }} | {{ n.mac or "" }} |
{% endfor %}
{% endif %}
---

[[servers/{{ entity.host }}/INDEX#{{ entity.host }}|← Back to {{ entity.host }}]]

[type: {{ entity.type }}] [name: {{ entity.name }}] [state: {{ entity.state }}] [last-seen: {{ entity.last_seen }}]
"""


def render_auto(entity: Entity) -> str:
    """Render an Entity to AUTO.md markdown."""
    env = Environment(autoescape=False, keep_trailing_newline=True)
    return env.from_string(_TEMPLATE).render(entity=entity)
